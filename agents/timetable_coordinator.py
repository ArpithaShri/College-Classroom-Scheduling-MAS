"""Timetable Coordinator Agent implementation for SPADE Multi-Agent System.

The central coordinating agent orchestrating multi-agent negotiation:
1. Receives scheduling requests (REQUEST) from DepartmentAgent.
2. Formulates candidate assignments (or consults the CSP engine).
3. Sequentially negotiates with FacultyAgent (PROPOSE), ClassroomAgent (ALLOCATE/PROPOSE),
   and StudentGroupAgent (CHECK_TIMETABLE).
4. Handles agent rejections, conflicts, and counter-proposals by triggering rescheduling (RESCHEDULE)
   and consulting the CSP engine for alternative domain values.
5. Issues confirmations (CONFIRM / FINAL_ACCEPT) once all autonomous agents reach consensus.
"""

import asyncio
import uuid
from typing import Optional, List, Dict, Tuple, Set, Any
from spade.behaviour import CyclicBehaviour
from spade.message import Message

from .base_agent import BaseAgent
from .communication import (
    REQUEST,
    PROPOSE,
    ALLOCATE,
    CHECK_TIMETABLE,
    ACCEPT,
    REJECT,
    RESCHEDULE,
    CONFIRM,
    CANCEL,
    FINAL_ACCEPT,
    parse_spade_message,
)
from scheduler.domain import (
    SchedulingProblem,
    Course,
    ScheduleValue,
    Assignment,
    generate_course_domain,
)
from scheduler.constraints import HardConstraintValidator, SoftConstraintEvaluator, UtilityWeights
from scheduler.csp_solver import CSPScheduler

class _RequestReplyBehaviour(CyclicBehaviour):
    """Send one XMPP request and wait for its matching reply."""

    async def send_and_receive(self, msg: Message, timeout: float):
        await self.send(msg)

        expected_jid = str(msg.to).split("/", 1)[0]
        _, request_payload = parse_spade_message(msg)
        correlation_id = request_payload.get("correlation_id")

        deadline = asyncio.get_running_loop().time() + timeout

        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(
                    f"No matching XMPP reply from {expected_jid} "
                    f"within {timeout} seconds"
                )

            reply = await self.receive(timeout=remaining)
            if reply is None:
                raise TimeoutError(
                    f"No matching XMPP reply from {expected_jid} "
                    f"within {timeout} seconds"
                )

            actual_sender = str(reply.sender).split("/", 1)[0]
            if actual_sender != expected_jid:
                continue

            response_performative, response_payload = parse_spade_message(reply)
            if correlation_id and (
                response_payload.get("correlation_id") != correlation_id
            ):
                continue

            self.agent.record_received_message(reply)
            return response_performative, response_payload



class AgentCommunicationError(RuntimeError):
    """Raised when a live agent exchange cannot be verified."""


class CoordinatorRequestHandler(CyclicBehaviour):
    """Receives coordinator requests and correlated agent responses."""

    async def run(self):
        msg = await self.receive(timeout=1.0)
        if msg is None:
            return

        agent: "TimetableCoordinatorAgent" = self.agent
        performative, payload = agent.record_received_message(msg)
        if performative == REQUEST:
            task = asyncio.create_task(
                agent.coordinate_request(
                    msg.sender, payload, behavior=self
                )
            )
            agent._request_tasks.add(task)

            def report_request_failure(done_task: asyncio.Task) -> None:
                agent._request_tasks.discard(done_task)
                try:
                    done_task.result()
                except Exception as exc:
                    agent.logger.error(
                        "Coordinator request failed",
                        exc_info=(type(exc), exc, exc.__traceback__),
                    )

            task.add_done_callback(report_request_failure)
            return

        correlation_id = str(payload.get("correlation_id", ""))
        pending = agent._pending_replies.get(correlation_id)
        if pending is None:
            agent.log_communication(
                direction="LIVE",
                sender=str(msg.sender or "UNKNOWN"),
                receiver=str(msg.to or agent.jid),
                performative=performative,
                payload=payload,
                status="UNMATCHED",
                reason="No pending request has this correlation ID",
            )
            return

        expected_sender, future = pending
        expected_recipient = str(agent.jid)
        if (
            not msg.sender
            or not msg.to
            or agent._bare_jid(msg.sender) != agent._bare_jid(expected_sender)
            or agent._bare_jid(msg.to) != agent._bare_jid(expected_recipient)
            or msg.thread != correlation_id
        ):
            agent.log_communication(
                direction="LIVE",
                sender=str(msg.sender or "UNKNOWN"),
                receiver=str(msg.to or agent.jid),
                performative=performative,
                payload=payload,
                status="UNMATCHED",
                reason="Sender, recipient, or correlation ID did not match",
            )
            return

        if not future.done():
            future.set_result((performative, payload))

    async def send_and_wait(
        self,
        to_jid: str,
        performative: str,
        payload: Dict[str, Any],
        timeout: float,
    ) -> Tuple[str, Dict[str, Any]]:
        """Send over SPADE and wait for the matching agent reply."""
        agent: "TimetableCoordinatorAgent" = self.agent
        correlation_id = str(uuid.uuid4())
        request_payload = dict(payload)
        request_payload["correlation_id"] = correlation_id
        msg = agent.make_message(
            to=to_jid,
            performative=performative,
            payload=request_payload,
            thread=correlation_id,
        )
        future = asyncio.get_running_loop().create_future()
        agent._pending_replies[correlation_id] = (to_jid, future)

        agent.log_communication(
            direction="SENT",
            sender=str(agent.jid),
            receiver=to_jid,
            performative=performative,
            payload=request_payload,
            status="ATTEMPTED",
        )
        try:
            try:
                await self.send(msg)
            except Exception as exc:
                agent.log_communication(
                    direction="SENT",
                    sender=str(agent.jid),
                    receiver=to_jid,
                    performative=performative,
                    payload=request_payload,
                    status="FAILED",
                    reason=str(exc),
                )
                raise AgentCommunicationError(
                    f"Could not transmit {performative} to {to_jid}"
                ) from exc

            agent.log_communication(
                direction="SENT",
                sender=str(agent.jid),
                receiver=to_jid,
                performative=performative,
                payload=request_payload,
                status="TRANSMITTED",
            )
            try:
                return await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError as exc:
                agent.log_communication(
                    direction="LIVE",
                    sender=to_jid,
                    receiver=str(agent.jid),
                    performative=performative,
                    payload=request_payload,
                    status="TIMEOUT",
                    reason=f"No correlated reply within {timeout:g} seconds",
                )
                raise AgentCommunicationError(
                    f"Timed out waiting for {to_jid} to reply to "
                    f"{performative}"
                ) from exc
        finally:
            agent._pending_replies.pop(correlation_id, None)


class TimetableCoordinatorAgent(BaseAgent):
    """Autonomous agent coordinating the multi-agent scheduling and conflict resolution process."""

    def __init__(
        self,
        jid: str,
        password: Optional[str] = None,
        scheduling_problem: Optional[SchedulingProblem] = None,
        **kwargs,
    ):
        super().__init__(jid=jid, password=password, role="TimetableCoordinatorAgent", **kwargs)

        # Domain problem knowledge & CSP solver
        self.problem = scheduling_problem or SchedulingProblem()
        self.csp_scheduler = CSPScheduler(self.problem, enable_logging=False)

        # Agent directory mapping entity ID -> Agent JID
        self.faculty_agents: Dict[str, str] = {}
        self.classroom_agents: Dict[str, str] = {}
        self.student_group_agents: Dict[str, str] = {}
        self.department_agents: Dict[str, str] = {}

        # Confirmed assignments history
        self.confirmed_assignments: List[Dict[str, Any]] = []
        self._message_handler: Optional[CoordinatorRequestHandler] = None
        self._pending_replies: Dict[str, Tuple[str, Any]] = {}
        self._request_tasks: Set[asyncio.Task] = set()

    async def setup(self):
        """Register CyclicBehaviour on startup."""
        await super().setup()
        handler = CoordinatorRequestHandler()
        self._message_handler = handler
        self.add_behaviour(handler)

    async def stop(self):
        """Cancel request tasks before stopping the coordinator agent."""
        for task in self._request_tasks:
            task.cancel()
        if self._request_tasks:
            await asyncio.gather(
                *self._request_tasks, return_exceptions=True
            )
        self._request_tasks.clear()
        await super().stop()

    @staticmethod
    def _bare_jid(jid: Any) -> str:
        return str(jid or "").split("/", 1)[0]

    def register_faculty_agent(self, faculty_id: str, jid: str):
        """Register JID for a Faculty Agent."""
        self.faculty_agents[faculty_id] = str(jid)

    def register_classroom_agent(self, room_id: str, jid: str):
        """Register JID for a Classroom Agent."""
        self.classroom_agents[room_id] = str(jid)

    def register_student_group_agent(self, group_id: str, jid: str):
        """Register JID for a Student Group Agent."""
        self.student_group_agents[group_id] = str(jid)

    def register_department_agent(self, dept_id: str, jid: str):
        """Register JID for a Department Agent."""
        self.department_agents[dept_id] = str(jid)

    def get_candidate_values_from_csp(
        self,
        course_dict: Dict[str, Any],
        excluded_candidates: Set[Tuple[str, str, str]],
    ) -> List[ScheduleValue]:
        """Query domain generator and soft-constraint scorer for prioritized candidate slots."""
        course = Course(
            id=course_dict.get("course_id", "C001"),
            name=course_dict.get("course_name", "Course"),
            faculty_id=course_dict.get("faculty_id", "F001"),
            student_group_id=course_dict.get("student_group_id", "CSE-A"),
            enrollment=int(course_dict.get("enrollment", 50)),
            duration=int(course_dict.get("duration", 1)),
            is_lab=bool(course_dict.get("is_lab", False)),
        )

        # Ensure problem knows about this course if not already present
        if not self.problem.get_course(course.id):
            self.problem.courses.append(course)
            self.problem.rebuild_indices()

        domain = generate_course_domain(course, self.problem)

        # Filter out previously rejected/conflicted candidates
        assigned = [
            Assignment(
                course_id=c["course_id"],
                course_name=c.get("course_name", c["course_id"]),
                faculty_id=c["faculty_id"],
                student_group_id=c["student_group_id"],
                room_id=c["room_id"],
                day=c["day"],
                start_time=c["start_time"],
                duration=int(c.get("duration", 1)),
                is_lab=bool(c.get("is_lab", False)),
                enrollment=int(c.get("enrollment", 0)),
            )
            for c in self.confirmed_assignments
        ]
        valid_candidates = [
            value
            for value in domain
            if (value.room_id, value.day, value.start_time)
            not in excluded_candidates
            and HardConstraintValidator.is_consistent(
                course, value, assigned, self.problem
            )[0]
        ]

        # Score only candidates that satisfy the current hard constraints.
        weights = UtilityWeights()

        pref_day = course_dict.get("day")
        pref_time = course_dict.get("start_time")

        scored_candidates = []
        for val in valid_candidates:
            score = SoftConstraintEvaluator.evaluate_assignment_utility(
                course=course,
                val=val,
                current_assignments=assigned,
                problem=self.problem,
                weights=weights,
            )
            # Boost score if candidate preserves requested day/time preferences
            if pref_day and val.day == pref_day:
                score += 0.25
            if pref_time and val.start_time == pref_time:
                score += 0.35

            scored_candidates.append((score, val))

        # Sort by score descending (highest utility first)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return [val for _, val in scored_candidates]

   
    async def send_and_await_reply(
        self,
        to_jid: str,
        performative: str,
        payload: Dict[str, Any],
        timeout: float = 2.0,
        direct_target_agent: Optional[BaseAgent] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Transmit a SPADE Message to recipient agent and await response message."""
        msg = self.make_message(to=to_jid, performative=performative, payload=payload)
        self.log_communication(
            direction="SENT",
            sender=str(self.jid),
            receiver=str(to_jid),
            performative=performative,
            payload=payload,
        )

        # 1. Real SPADE message transmission when agent is live
        if self.is_alive():
            try:
                await self.send(msg)
            except Exception as e:
                self.logger.debug(f"Direct spade send error: {e}")

            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                if hasattr(self, "inbox"):
                    try:
                        resp_msg = await asyncio.wait_for(self.inbox.get(), timeout=0.1)
                        if resp_msg:
                            resp_perf, resp_payload = self.record_received_message(resp_msg)
                            return resp_perf, resp_payload
                    except asyncio.TimeoutError:
                        pass
                await asyncio.sleep(0.02)

        # 2. In-process message dispatch fallback for offline unit tests
        if direct_target_agent is not None:
            correlation_id = str(uuid.uuid4())
            simulated_payload = dict(payload)
            simulated_payload["correlation_id"] = correlation_id
            msg = self.make_message(
                to=to_jid,
                performative=performative,
                payload=simulated_payload,
                thread=correlation_id,
            )
            self.log_communication(
                direction="SIMULATED",
                sender=str(self.jid),
                receiver=str(to_jid),
                performative=performative,
                payload=simulated_payload,
                status="SENT",
            )
            direct_target_agent.record_received_message(
                msg, simulated=True
            )
            reply_msg = direct_target_agent.process_incoming_message(
                sender=str(self.jid),
                performative=performative,
                payload=simulated_payload,
            )

            if reply_msg:
                resp_perf, resp_payload = parse_spade_message(reply_msg)
                if (
                    resp_payload.get("correlation_id") != correlation_id
                    or self._bare_jid(reply_msg.sender)
                    != self._bare_jid(direct_target_agent.jid)
                ):
                    raise AgentCommunicationError(
                        "In-process agent returned an uncorrelated response."
                    )
                direct_target_agent.log_communication(
                    direction="SIMULATED",
                    sender=str(direct_target_agent.jid),
                    receiver=str(self.jid),
                    performative=resp_perf,
                    payload=resp_payload,
                    status="SENT",
                )
                self.log_communication(
                    direction="SIMULATED",
                    sender=str(direct_target_agent.jid),
                    receiver=str(self.jid),
                    performative=resp_perf,
                    payload=resp_payload,
                    status="RECEIVED",
                )
                return resp_perf, resp_payload

        self.log_communication(
            direction="SIMULATED",
            sender=str(self.jid),
            receiver=str(to_jid),
            performative=performative,
            payload=payload,
            status="NO_TARGET",
            reason="No in-process agent target is registered",
        )
        return REJECT, {"reason": "No in-process agent target is registered"}

    async def coordinate_course_negotiation(
        self,
        request_payload: Dict[str, Any],
        faculty_agent: Optional[BaseAgent] = None,
        classroom_agents_map: Optional[Dict[str, BaseAgent]] = None,
        student_group_agent: Optional[BaseAgent] = None,
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """Execute step-by-step multi-agent negotiation using SPADE Message passing.

        Transmits:
        1. FacultyAgent (PROPOSE Message)
        2. ClassroomAgent (ALLOCATE Message)
        3. StudentGroupAgent (CHECK_TIMETABLE Message)
        4. Confirmations (CONFIRM Message)
        """
        course_id = request_payload.get("course_id", "")
        course_name = request_payload.get("course_name", course_id)
        faculty_id = request_payload.get("faculty_id", "")
        student_group_id = request_payload.get("student_group_id", "")
        enrollment = int(request_payload.get("enrollment", 0))
        duration = int(request_payload.get("duration", 1))
        room_type = request_payload.get("room_type", "classroom")
        is_lab = bool(request_payload.get("is_lab", False))

        # Initial requested preference if specified
        pref_day = request_payload.get("day")
        pref_time = request_payload.get("start_time")
        pref_room = request_payload.get("room_id")

        excluded_candidates: Set[Tuple[str, str, str]] = set()

        # Build candidate generator
        candidates: List[Tuple[str, str, str]] = []
        if pref_room and pref_day and pref_time:
            candidates.append((pref_room, pref_day, pref_time))

        csp_candidates = self.get_candidate_values_from_csp(
            request_payload, excluded_candidates
        )
        for val in csp_candidates:
            tup = (val.room_id, val.day, val.start_time)
            if tup not in candidates:
                candidates.append(tup)

        while candidates:
            room_id, day, start_time = candidates.pop(0)
            candidate_tuple = (room_id, day, start_time)

            if candidate_tuple in excluded_candidates:
                continue

            current_proposal = {
                "course_id": course_id,
                "course_name": course_name,
                "faculty_id": faculty_id,
                "student_group_id": student_group_id,
                "room_id": room_id,
                "day": day,
                "start_time": start_time,
                "duration": duration,
                "enrollment": enrollment,
                "room_type": getattr(
                    self.problem.get_room(room_id),
                    "room_type",
                    room_type,
                ),
                "is_lab": is_lab,
            }

            # ----------------------------------------------------
            # 1. Faculty Agent Negotiation (PROPOSE Message)
            # ----------------------------------------------------
            fac_jid = self.faculty_agents.get(faculty_id, f"faculty_{faculty_id.lower()}@localhost")
            fac_resp_type, fac_resp = await self.send_and_await_reply(
                to_jid=fac_jid,
                performative=PROPOSE,
                payload=current_proposal,
                direct_target_agent=faculty_agent,
            )

            if fac_resp_type != ACCEPT:
                fac_reason = fac_resp.get("reason", "Faculty unavailable")
                self.logger.warning(
                    f"Coordinator: Faculty rejected {candidate_tuple} - Reason: {fac_reason}"
                )
                excluded_candidates.add(candidate_tuple)
                # Reschedule with CSP
                self.log_communication(
                    direction="APPLICATION",
                    sender=str(self.jid),
                    receiver=str(self.jid),
                    performative=RESCHEDULE,
                    payload={"reason": fac_reason, "failed_candidate": current_proposal},
                    status="RESCHEDULE",
                )
                continue

            # ----------------------------------------------------
            # 2. Classroom Agent Negotiation (ALLOCATE Message)
            # ----------------------------------------------------
            cls_jid = self.classroom_agents.get(room_id, f"classroom_{room_id.lower()}@localhost")
            cls_target = classroom_agents_map.get(room_id) if classroom_agents_map else None
            cls_resp_type, cls_resp = await self.send_and_await_reply(
                to_jid=cls_jid,
                performative=ALLOCATE,
                payload=current_proposal,
                direct_target_agent=cls_target,
            )

            if cls_resp_type != ACCEPT:
                cls_reason = cls_resp.get("reason", "Room constraint violated")
                self.logger.warning(
                    f"Coordinator: Classroom rejected {candidate_tuple} - Reason: {cls_reason}"
                )
                excluded_candidates.add(candidate_tuple)
                # Reschedule with CSP
                self.log_communication(
                    direction="APPLICATION",
                    sender=str(self.jid),
                    receiver=str(self.jid),
                    performative=RESCHEDULE,
                    payload={"reason": cls_reason, "failed_candidate": current_proposal},
                    status="RESCHEDULE",
                )
                # Refresh CSP candidates excluding failed rooms/slots
                more_csp = self.get_candidate_values_from_csp(request_payload, excluded_candidates)
                for v in more_csp:
                    t = (v.room_id, v.day, v.start_time)
                    if t not in candidates and t not in excluded_candidates:
                        candidates.append(t)
                continue

            # ----------------------------------------------------
            # 3. Student Group Agent Negotiation (CHECK_TIMETABLE Message)
            # ----------------------------------------------------
            sg_jid = self.student_group_agents.get(
                student_group_id, f"studentgroup_{student_group_id.lower()}@localhost"
            )
            sg_resp_type, sg_resp = await self.send_and_await_reply(
                to_jid=sg_jid,
                performative=CHECK_TIMETABLE,
                payload=current_proposal,
                direct_target_agent=student_group_agent,
            )

            if sg_resp_type != ACCEPT:
                sg_reason = sg_resp.get("reason", "Student timetable conflict")
                self.logger.warning(
                    f"Coordinator: StudentGroup reported conflict {candidate_tuple} - Reason: {sg_reason}"
                )
                excluded_candidates.add(candidate_tuple)
                # Reschedule with CSP
                self.log_communication(
                    direction="APPLICATION",
                    sender=str(self.jid),
                    receiver=str(self.jid),
                    performative=RESCHEDULE,
                    payload={"reason": sg_reason, "failed_candidate": current_proposal},
                    status="RESCHEDULE",
                )
                # Refresh CSP candidates
                more_csp = self.get_candidate_values_from_csp(request_payload, excluded_candidates)
                for v in more_csp:
                    t = (v.room_id, v.day, v.start_time)
                    if t not in candidates and t not in excluded_candidates:
                        candidates.append(t)
                continue

           
            # 4. Confirm with all participating agents and verify every reply.
            final_schedule = dict(current_proposal)
            final_schedule["status"] = "SCHEDULED"

            confirmation_targets = [
                (fac_jid, faculty_agent, "Faculty"),
                (cls_jid, cls_target, "Classroom"),
                (sg_jid, student_group_agent, "Student group"),
            ]

            confirmation_failures = []
            confirmed_targets = []
            confirmation_attempted_targets = []

            for target_jid, target_agent, agent_name in confirmation_targets:
                target = (target_jid, target_agent, agent_name)
                confirmation_attempted_targets.append(target)
                try:
                    response_type, response_payload = await self.send_and_await_reply(
                        to_jid=target_jid,
                        performative=CONFIRM,
                        payload=final_schedule,
                        direct_target_agent=target_agent,
                    )
                except Exception:
                    await self._cancel_confirmed_targets(
                        confirmation_attempted_targets, final_schedule
                    )
                    raise

                if response_type == ACCEPT:
                    confirmed_targets.append(target)
                else:
                    confirmation_failures.append({
                        "agent": agent_name,
                        "response": response_type,
                        "reason": response_payload.get(
                            "reason", "Confirmation was not accepted"
                        ),
                    })

            if confirmation_failures:
                await self._cancel_confirmed_targets(
                    confirmed_targets, final_schedule
                )
                self.log_communication(
                    direction="APPLICATION",
                    sender=str(self.jid),
                    receiver=str(self.jid),
                    performative=RESCHEDULE,
                    payload={
                        "course_id": course_id,
                        "failed_candidate": final_schedule,
                        "confirmation_failures": confirmation_failures,
                    },
                    status="RESCHEDULE",
                )
                self.logger.warning(
                    "Confirmation failed for %s: %s",
                    course_id,
                    confirmation_failures,
                )
                excluded_candidates.add(candidate_tuple)
                more_csp = self.get_candidate_values_from_csp(
                    request_payload, excluded_candidates
                )
                for value in more_csp:
                    alternative = (value.room_id, value.day, value.start_time)
                    if alternative not in candidates and alternative not in excluded_candidates:
                        candidates.append(alternative)
                continue

            self.confirmed_assignments.append(final_schedule)

            self.log_communication(
                direction="APPLICATION",
                sender=str(self.jid),
                receiver=str(self.jid),
                performative=FINAL_ACCEPT,
                payload=final_schedule,
                status="SCHEDULED",
            )

            return True, final_schedule, "Consensus reached across all agents."

        return (
            False,
            None,
            "No candidate passed agent negotiation and confirmation.",
        )

    async def _cancel_confirmed_targets(
        self,
        targets: List[Tuple[str, Optional[BaseAgent], str]],
        assignment: Dict[str, Any],
    ) -> None:
        """Compensate local agent bookings before abandoning a proposal."""
        cancellation_failures = []
        for target_jid, target_agent, agent_name in targets:
            try:
                response_type, response_payload = await self.send_and_await_reply(
                    to_jid=target_jid,
                    performative=CANCEL,
                    payload=assignment,
                    direct_target_agent=target_agent,
                )
            except Exception as exc:
                cancellation_failures.append(f"{agent_name}: {exc}")
                continue

            if response_type != ACCEPT:
                cancellation_failures.append(
                    response_payload.get(
                        "reason", f"{agent_name} did not cancel its booking"
                    )
                )

        if cancellation_failures:
            raise AgentCommunicationError(
                "Could not safely release all provisional agent bookings: "
                + "; ".join(cancellation_failures)
            )


    async def coordinate_request(
        self,
        sender: Any,
        payload: Dict[str, Any],
        behavior: Optional[CoordinatorRequestHandler] = None,
    ):
        """Asynchronously coordinate request when received through SPADE message loop."""
        success, final_assignment, reason = await self.coordinate_course_negotiation(payload)
        resp_payload = final_assignment or {
            "type": REJECT,
            "course_id": payload.get("course_id", ""),
            "reason": reason,
        }
        performative = FINAL_ACCEPT if success else REJECT
        await self.send_message(
            to=str(sender),
            performative=performative,
            payload=resp_payload,
            behavior=behavior,
        )
