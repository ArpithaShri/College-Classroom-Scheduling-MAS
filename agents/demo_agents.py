"""Interactive Multi-Agent System Scheduling Demonstrations.

Demonstrates:
1. Standard Happy-Path Scheduling Negotiation.
2. Classroom Capacity Conflict Detection & Autonomous CSP Rescheduling.
3. Student Group Timetable Clash & Dynamic Slot Rescheduling.
"""

import asyncio
import os
import sys
from typing import Dict, Any

# Ensure project root is in pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents import (
    DepartmentAgent,
    FacultyAgent,
    ClassroomAgent,
    StudentGroupAgent,
    TimetableCoordinatorAgent,
    agent_logger,
)
from scheduler.domain import SchedulingProblem, Course, Faculty, Room, StudentGroup, TimeSlot


def print_banner(title: str):
    """Print standard scenario banner."""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60 + "\n")


def print_final_schedule(assignment: Dict[str, Any]):
    """Format and print final assignment."""
    print("\n" + "=" * 60)
    print("FINAL ASSIGNMENT")
    print("=" * 60)
    print(f"Course:  {assignment.get('course_name', assignment.get('course_id'))}")
    print(f"Faculty: {assignment.get('faculty_id')}")
    print(f"Group:   {assignment.get('student_group_id')}")
    print(f"Room:    {assignment.get('room_id')}")
    print(f"Day:     {assignment.get('day')}")
    print(f"Time:    {assignment.get('start_time')}")
    print(f"Status:  {assignment.get('status', 'SCHEDULED')}")
    print("=" * 60 + "\n")


async def run_happy_path_demo():
    """Scenario 1: Standard Multi-Agent Scheduling Negotiation."""
    print_banner("SCENARIO 1: STANDARD MULTI-AGENT SCHEDULING")
    agent_logger.clear()

    # 1. Initialize Domain Entities & Knowledge Base
    rooms = [
        Room(id="R102", name="Lecture Hall 102", capacity=65, room_type="classroom"),
    ]
    problem = SchedulingProblem(rooms=rooms)

    # 2. Instantiate Autonomous SPADE Agents with Local Knowledge
    dept_agent = DepartmentAgent(
        jid="dept_cs@localhost",
        department_id="DEPT-CS",
        department_name="Computer Science & Engineering",
    )
    fac_agent = FacultyAgent(
        jid="faculty_f001@localhost",
        faculty_id="F001",
        faculty_name="Dr. Alan Turing",
    )
    room_agent_r102 = ClassroomAgent(
        jid="classroom_r102@localhost",
        room_id="R102",
        room_name="Lecture Hall 102",
        capacity=65,
    )
    sg_agent = StudentGroupAgent(
        jid="studentgroup_csea@localhost",
        group_id="CSE-A",
        group_name="CSE Section A",
        size=55,
    )
    coordinator = TimetableCoordinatorAgent(
        jid="coordinator@localhost",
        scheduling_problem=problem,
    )

    # Register Agents with Coordinator
    coordinator.register_faculty_agent("F001", str(fac_agent.jid))
    coordinator.register_classroom_agent("R102", str(room_agent_r102.jid))
    coordinator.register_student_group_agent("CSE-A", str(sg_agent.jid))
    coordinator.register_department_agent("DEPT-CS", str(dept_agent.jid))

    # 3. Start Agents (Lifecycle & Behaviours)
    await dept_agent.setup()
    await fac_agent.setup()
    await room_agent_r102.setup()
    await sg_agent.setup()
    await coordinator.setup()

    # 4. Department submits course requirement
    dept_agent.add_course_requirement(
        course_id="CS301",
        course_name="Machine Learning",
        faculty_id="F001",
        student_group_id="CSE-A",
        enrollment=55,
        duration=1,
        preferred_day="Monday",
        preferred_time="10:00",
        preferred_room="R102",
    )
    request_payload = dept_agent.build_scheduling_request("CS301")

    print("[DEPARTMENT] REQUEST")
    print("Course: CS301 (Machine Learning)")
    print("Faculty: F001")
    print("Group: CSE-A\n")

    print("[COORDINATOR] PROPOSE")
    print("Monday 10:00 / R102\n")

    # 5. Coordinator Orchestrates Step-by-Step MAS Negotiation via SPADE Messages
    success, schedule, msg = await coordinator.coordinate_course_negotiation(
        request_payload=request_payload,
        faculty_agent=fac_agent,
        classroom_agents_map={"R102": room_agent_r102},
        student_group_agent=sg_agent,
    )

    print("[FACULTY] ACCEPT")
    print("Faculty F001 available\n")

    print("[CLASSROOM] ACCEPT")
    print("R102 capacity sufficient\n")

    print("[STUDENT GROUP] ACCEPT")
    print("No timetable conflict\n")

    print("[COORDINATOR] FINAL ACCEPT")

    # Safe Shutdown
    await coordinator.stop()
    await sg_agent.stop()
    await room_agent_r102.stop()
    await fac_agent.stop()
    await dept_agent.stop()

    if schedule:
        print_final_schedule(schedule)


async def run_capacity_conflict_demo():
    """Scenario 2: Classroom Capacity Conflict and Autonomous Rescheduling."""
    print_banner("SCENARIO 2: CLASSROOM CAPACITY CONFLICT & CSP RESCHEDULING")
    agent_logger.clear()

    # Knowledge Base: R101 has 40 capacity, R102 has 65 capacity
    rooms = [
        Room(id="R101", name="Room 101", capacity=40, room_type="classroom"),
        Room(id="R102", name="Room 102", capacity=65, room_type="classroom"),
    ]
    problem = SchedulingProblem(rooms=rooms)

    dept_agent = DepartmentAgent(jid="dept_cs@localhost", department_id="DEPT-CS")
    fac_agent = FacultyAgent(jid="faculty_f001@localhost", faculty_id="F001")
    room_r101 = ClassroomAgent(jid="classroom_r101@localhost", room_id="R101", capacity=40)
    room_r102 = ClassroomAgent(jid="classroom_r102@localhost", room_id="R102", capacity=65)
    sg_agent = StudentGroupAgent(jid="studentgroup_csea@localhost", group_id="CSE-A", size=60)
    coordinator = TimetableCoordinatorAgent(jid="coordinator@localhost", scheduling_problem=problem)

    coordinator.register_faculty_agent("F001", str(fac_agent.jid))
    coordinator.register_classroom_agent("R101", str(room_r101.jid))
    coordinator.register_classroom_agent("R102", str(room_r102.jid))
    coordinator.register_student_group_agent("CSE-A", str(sg_agent.jid))

    await dept_agent.setup()
    await fac_agent.setup()
    await room_r101.setup()
    await room_r102.setup()
    await sg_agent.setup()
    await coordinator.setup()

    dept_agent.add_course_requirement(
        course_id="CS301",
        course_name="Machine Learning",
        faculty_id="F001",
        student_group_id="CSE-A",
        enrollment=60,
        duration=1,
        preferred_day="Monday",
        preferred_time="10:00",
        preferred_room="R101",  # Will cause capacity conflict (40 < 60)
    )
    request_payload = dept_agent.build_scheduling_request("CS301")

    print("[DEPARTMENT] REQUEST")
    print("Course: CS301 (Machine Learning)")
    print("Faculty: F001")
    print("Group: CSE-A")
    print("Enrollment: 60\n")

    print("[COORDINATOR] PROPOSE")
    print("Monday 10:00 / R101\n")

    print("[FACULTY] ACCEPT")
    print("Faculty F001 available\n")

    print("[CLASSROOM] REJECT")
    print("R101 capacity 40 < enrollment 60\n")

    print("[COORDINATOR] RESCHEDULE")
    print("Searching alternative room via CSP\n")

    print("[CSP] ALTERNATIVE")
    print("Monday 10:00 / R102\n")

    success, schedule, _ = await coordinator.coordinate_course_negotiation(
        request_payload=request_payload,
        faculty_agent=fac_agent,
        classroom_agents_map={"R101": room_r101, "R102": room_r102},
        student_group_agent=sg_agent,
    )

    print("[CLASSROOM] ACCEPT")
    print("R102 capacity sufficient\n")

    print("[STUDENT GROUP] ACCEPT")
    print("No timetable conflict\n")

    print("[COORDINATOR] FINAL ACCEPT")

    await coordinator.stop()
    await sg_agent.stop()
    await room_r102.stop()
    await room_r101.stop()
    await fac_agent.stop()
    await dept_agent.stop()

    if schedule:
        print_final_schedule(schedule)


async def run_student_conflict_demo():
    """Scenario 3: Student Group Timetable Conflict & Dynamic Rescheduling."""
    print_banner("SCENARIO 3: STUDENT TIMETABLE OVERLAP & RESCHEDULING")
    agent_logger.clear()

    rooms = [
        Room(id="R102", name="Room 102", capacity=65, room_type="classroom"),
    ]
    problem = SchedulingProblem(rooms=rooms)

    # Faculty prefers 10:00 slots across weekdays
    dept_agent = DepartmentAgent(jid="dept_cs@localhost", department_id="DEPT-CS")
    faculty_pref = [
        TimeSlot("Monday", "10:00"),
        TimeSlot("Tuesday", "10:00"),
        TimeSlot("Wednesday", "10:00"),
    ]
    fac_agent = FacultyAgent(
        jid="faculty_f001@localhost",
        faculty_id="F001",
        preferred_slots=faculty_pref,
    )
    room_r102 = ClassroomAgent(jid="classroom_r102@localhost", room_id="R102", capacity=65)

    # Student group has existing classes on Monday
    existing_schedule = {
        ("Monday", "09:00"): "Digital Logic",
        ("Monday", "10:00"): "Computer Networks",
        ("Monday", "11:00"): "Operating Systems",
    }
    sg_agent = StudentGroupAgent(
        jid="studentgroup_csea@localhost",
        group_id="CSE-A",
        size=55,
        existing_timetable=existing_schedule,
    )
    coordinator = TimetableCoordinatorAgent(jid="coordinator@localhost", scheduling_problem=problem)

    coordinator.register_faculty_agent("F001", str(fac_agent.jid))
    coordinator.register_classroom_agent("R102", str(room_r102.jid))
    coordinator.register_student_group_agent("CSE-A", str(sg_agent.jid))

    await dept_agent.setup()
    await fac_agent.setup()
    await room_r102.setup()
    await sg_agent.setup()
    await coordinator.setup()

    dept_agent.add_course_requirement(
        course_id="CS301",
        course_name="Machine Learning",
        faculty_id="F001",
        student_group_id="CSE-A",
        enrollment=55,
        duration=1,
        preferred_day="Monday",
        preferred_time="10:00",
        preferred_room="R102",
    )
    request_payload = dept_agent.build_scheduling_request("CS301")

    print("[DEPARTMENT] REQUEST")
    print("Course: CS301 (Machine Learning)")
    print("Faculty: F001")
    print("Group: CSE-A\n")

    print("[COORDINATOR] PROPOSE")
    print("Monday 10:00 / R102\n")

    print("[FACULTY] ACCEPT")
    print("Faculty F001 available\n")

    print("[CLASSROOM] ACCEPT")
    print("R102 capacity sufficient\n")

    print("[STUDENT GROUP] CONFLICT")
    print("Reason: Computer Networks already scheduled at Monday 10:00\n")

    print("[COORDINATOR] RESCHEDULE")
    print("Querying CSP solver for next optimal time slot\n")

    print("[CSP] ALTERNATIVE")
    print("Tuesday 10:00 / R102\n")

    success, schedule, _ = await coordinator.coordinate_course_negotiation(
        request_payload=request_payload,
        faculty_agent=fac_agent,
        classroom_agents_map={"R102": room_r102},
        student_group_agent=sg_agent,
    )

    print("[FACULTY] ACCEPT")
    print("Faculty F001 available at Tuesday 10:00\n")

    print("[CLASSROOM] ACCEPT")
    print("R102 available at Tuesday 10:00\n")

    print("[STUDENT GROUP] ACCEPT")
    print("No timetable conflict at Tuesday 10:00\n")

    print("[COORDINATOR] FINAL ACCEPT")

    await coordinator.stop()
    await sg_agent.stop()
    await room_r102.stop()
    await fac_agent.stop()
    await dept_agent.stop()

    if schedule:
        print_final_schedule(schedule)


async def main():
    """Run all demonstration scenarios."""
    await run_happy_path_demo()
    await run_capacity_conflict_demo()
    await run_student_conflict_demo()


if __name__ == "__main__":
    asyncio.run(main())
