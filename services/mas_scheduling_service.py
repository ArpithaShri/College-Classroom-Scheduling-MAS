
"""Orchestration service for the classroom scheduling MAS."""

import logging
import re
from typing import Any, Dict, List, Optional

from config import Config
from scheduler.csp_solver import CSPScheduler
from scheduler.domain import SchedulingProblem

from agents.timetable_coordinator import TimetableCoordinatorAgent
from agents.faculty_agent import FacultyAgent
from agents.classroom_agent import ClassroomAgent
from agents.student_group_agent import StudentGroupAgent


logger = logging.getLogger(__name__)


class MASSchedulingError(RuntimeError):
    """Raised when scheduling or agent negotiation fails."""


class MASTimetableService:
    """Run CSP scheduling and negotiate assignments through agents."""

    def __init__(
        self,
        problem: SchedulingProblem,
        password: Optional[str] = None,
        xmpp_domain: Optional[str] = None,
        live_xmpp: bool = False,
    ):
        if problem is None:
            raise ValueError("A SchedulingProblem is required.")

        self.problem = problem
        self.password = password or Config.XMPP_PASSWORD
        self.live_xmpp = live_xmpp
        self.xmpp_domain = (
            xmpp_domain
            or getattr(Config, "XMPP_DOMAIN", None)
            or "localhost"
        )

        self.coordinator = None
        self.agents: List[Any] = []
        self.started_agents: List[Any] = []
        self.faculty_agents: Dict[Any, Any] = {}
        self.classroom_agents: Dict[Any, Any] = {}
        self.student_group_agents: Dict[Any, Any] = {}

    @staticmethod
    def _safe_id(value: Any) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", str(value))
        return cleaned.strip("_") or "unknown"

    def _jid(self, role: str, entity_id: Any) -> str:
        return (
            f"{role}_{self._safe_id(entity_id)}"
            f"@{self.xmpp_domain}"
        )

    def _build_agents(self) -> None:
        """Create agents and register their JIDs with the coordinator."""
        self.coordinator = TimetableCoordinatorAgent(
            jid=self._jid("coordinator", "main"),
            password=self.password,
            scheduling_problem=self.problem,
        )

        self.agents = []
        self.faculty_agents = {}
        self.classroom_agents = {}
        self.student_group_agents = {}

        for faculty in self.problem.faculty:
            agent = FacultyAgent(
                jid=self._jid("faculty", faculty.id),
                password=self.password,
                faculty_id=faculty.id,
                faculty_name=getattr(
                    faculty, "name", str(faculty.id)
                ),
                available_slots=getattr(
                    faculty, "available_slots", None
                ),
                preferred_slots=getattr(
                    faculty, "preferred_slots", None
                ),
                max_daily_hours=getattr(
                    faculty, "max_daily_hours", 6
                ),
                max_consecutive_hours=getattr(
                    faculty, "max_consecutive_hours", 3
                ),
            )

            self.faculty_agents[faculty.id] = agent
            self.coordinator.register_faculty_agent(
                faculty.id, str(agent.jid)
            )
            self.agents.append(agent)

        for room in self.problem.rooms:
            agent = ClassroomAgent(
                jid=self._jid("classroom", room.id),
                password=self.password,
                room_id=room.id,
                room_name=getattr(
                    room, "name", str(room.id)
                ),
                capacity=room.capacity,
                room_type=getattr(
                    room, "room_type", "classroom"
                ),
                available_slots=getattr(
                    room, "available_slots", None
                ),
            )

            self.classroom_agents[room.id] = agent
            self.coordinator.register_classroom_agent(
                room.id, str(agent.jid)
            )
            self.agents.append(agent)

        for group in self.problem.student_groups:
            agent = StudentGroupAgent(
                jid=self._jid("studentgroup", group.id),
                password=self.password,
                group_id=group.id,
                group_name=getattr(
                    group, "name", str(group.id)
                ),
                size=getattr(group, "size", 0),
                commitments=getattr(
                    group, "commitments", None
                ),
            )

            self.student_group_agents[group.id] = agent
            self.coordinator.register_student_group_agent(
                group.id, str(agent.jid)
            )
            self.agents.append(agent)

        self.agents.append(self.coordinator)

    async def _start_agents(self) -> None:
        """Start live SPADE agents and track successful starts."""
        for agent in self.agents:
            try:
                await agent.start(auto_register=True)
                self.started_agents.append(agent)
                logger.info("Started SPADE agent %s", agent.jid)
            except Exception as exc:
                raise MASSchedulingError(
                    f"Could not start SPADE agent {agent.jid}. "
                    "Check the XMPP server, JID domain, credentials, "
                    "and account registration settings."
                ) from exc

    async def _stop_agents(self) -> None:
        """Stop every agent that successfully started."""
        for agent in reversed(self.started_agents):
            try:
                await agent.stop()
                logger.info("Stopped SPADE agent %s", agent.jid)
            except Exception:
                logger.exception(
                    "Failed to stop SPADE agent %s", agent.jid
                )

        self.started_agents.clear()

    async def schedule(self) -> Dict[str, Any]:
        """Generate and negotiate a timetable without database persistence."""
        scheduler = CSPScheduler(
            problem=self.problem,
            enable_logging=False,
        )
        csp_result = scheduler.solve()

        if not csp_result.success:
            raise MASSchedulingError(
                "The CSP scheduler could not find a feasible timetable."
            )

        proposed_assignments = list(csp_result.schedule)

        if not proposed_assignments:
            raise MASSchedulingError(
                "The CSP solver returned no assignments."
            )

        self._build_agents()
        confirmed_assignments = []

        try:
            if self.live_xmpp:
                await self._start_agents()

            for proposed in proposed_assignments:
                course_id = proposed["course_id"]
                course = self.problem.get_course(course_id)

                if course is None:
                    raise MASSchedulingError(
                        f"Course {course_id!r} is missing from the "
                        "scheduling problem."
                    )

                request_payload = {
                    "course_id": course.id,
                    "course_name": course.name,
                    "faculty_id": course.faculty_id,
                    "student_group_id": course.student_group_id,
                    "enrollment": course.enrollment,
                    "duration": course.duration,
                    "is_lab": getattr(course, "is_lab", False),
                    "room_type": (
                        "lab"
                        if getattr(course, "is_lab", False)
                        else "classroom"
                    ),
                    "room_id": proposed["room_id"],
                    "day": proposed["day"],
                    "start_time": proposed["start_time"],
                }

                negotiation_kwargs = {}

                if not self.live_xmpp:
                    negotiation_kwargs = {
                        "faculty_agent": self.faculty_agents.get(
                            course.faculty_id
                        ),
                        "classroom_agents_map": self.classroom_agents,
                        "student_group_agent": (
                            self.student_group_agents.get(
                                course.student_group_id
                            )
                        ),
                    }

                success, assignment, reason = (
                    await self.coordinator.coordinate_course_negotiation(
                        request_payload=request_payload,
                        **negotiation_kwargs,
                    )
                )

                if not success or assignment is None:
                    raise MASSchedulingError(
                        f"Negotiation failed for course {course_id}: "
                        f"{reason}"
                    )

                confirmed_assignments.append(assignment)

            return {
                "success": True,
                "assignments": confirmed_assignments,
                "statistics": csp_result.statistics,
                "agent_count": len(self.agents),
                "negotiated_count": len(confirmed_assignments),
                "mode": (
                    "live_xmpp" if self.live_xmpp else "offline"
                ),
            }

        finally:
            await self._stop_agents()


async def generate_timetable_with_mas(
    problem: SchedulingProblem,
    password: Optional[str] = None,
    xmpp_domain: Optional[str] = None,
    live_xmpp: bool = False,
) -> Dict[str, Any]:
    """Convenience entry point for asynchronous callers."""
    service = MASTimetableService(
        problem=problem,
        password=password,
        xmpp_domain=xmpp_domain,
        live_xmpp=live_xmpp,
    )
    return await service.schedule()
