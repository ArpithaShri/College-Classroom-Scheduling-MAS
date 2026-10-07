"""Constraint Satisfaction Problem (CSP) Timetable Solver.

Implements a standalone CSP scheduler utilizing:
- Minimum Remaining Values (MRV) heuristic for variable selection
- Soft-constraint utility-based domain value ordering
- Forward checking constraint propagation with domain pruning
- Recursive backtracking search with complete state restoration
- Structured results and execution statistics
"""

import time
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set, Any

from .domain import (
    Course,
    Faculty,
    Room,
    StudentGroup,
    ScheduleValue,
    Assignment,
    SchedulingProblem,
    generate_course_domain,
)
from .constraints import (
    HardConstraintValidator,
    SoftConstraintEvaluator,
    UtilityWeights,
)

logger = logging.getLogger("scheduler.csp_solver")


@dataclass
class SolverResult:
    """Encapsulates the output of the CSP solver."""
    success: bool
    schedule: List[Dict[str, Any]]
    conflicts: List[str]
    statistics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "schedule": self.schedule,
            "conflicts": self.conflicts,
            "statistics": self.statistics,
        }


class CSPScheduler:
    """Standalone CSP Timetable Solver using MRV, Soft-Scored Value Ordering, and Backtracking."""

    def __init__(
        self,
        problem: SchedulingProblem,
        weights: Optional[UtilityWeights] = None,
        enable_logging: bool = False,
    ):
        self.problem = problem
        self.weights = weights or UtilityWeights()
        self.enable_logging = enable_logging

        # Solver Statistics
        self.assignments_tried = 0
        self.backtracks = 0
        self.start_time = 0.0
        self.end_time = 0.0
        self.trace_log: List[str] = []

    def _log(self, message: str):
        """Record debug and trace events."""
        if self.enable_logging:
            logger.info(message)
        self.trace_log.append(message)

    def generate_initial_domains(self) -> Dict[str, List[ScheduleValue]]:
        """Generate initial candidate domains for each course."""
        domains: Dict[str, List[ScheduleValue]] = {}
        for course in self.problem.courses:
            dom = generate_course_domain(course, self.problem)
            domains[course.id] = dom
        return domains

    def select_unassigned_variable_mrv(
        self,
        unassigned_courses: List[Course],
        current_domains: Dict[str, List[ScheduleValue]],
        current_assignments: List[Assignment],
    ) -> Course:
        """
        Minimum Remaining Values (MRV) Heuristic.
        
        Selects the unassigned course with the fewest remaining consistent domain values.
        Tie-breaker: Largest course duration, then largest enrollment.
        """
        def count_valid_domain(course: Course) -> int:
            raw_domain = current_domains.get(course.id, [])
            valid_count = 0
            for val in raw_domain:
                consistent, _ = HardConstraintValidator.is_consistent(
                    course, val, current_assignments, self.problem
                )
                if consistent:
                    valid_count += 1
            return valid_count

        return min(
            unassigned_courses,
            key=lambda c: (
                count_valid_domain(c),
                -c.duration,
                -c.enrollment,
                c.id,
            ),
        )

    def order_domain_values(
        self,
        course: Course,
        domain: List[ScheduleValue],
        current_assignments: List[Assignment],
    ) -> List[ScheduleValue]:
        """
        Order domain values by soft-constraint utility score in descending order.
        
        Ensures highest-quality assignments (faculty preference, room utilization, student convenience)
        are tried first.
        """
        scored_values = []
        for val in domain:
            utility = SoftConstraintEvaluator.evaluate_assignment_utility(
                course, val, current_assignments, self.problem, self.weights
            )
            scored_values.append((utility, val))

        # Sort descending by utility score
        scored_values.sort(key=lambda item: item[0], reverse=True)
        return [val for _, val in scored_values]

    def forward_check_and_prune(
        self,
        assigned_course: Course,
        assigned_value: ScheduleValue,
        unassigned_courses: List[Course],
        current_domains: Dict[str, List[ScheduleValue]],
        current_assignments: List[Assignment],
    ) -> Tuple[bool, Dict[str, List[ScheduleValue]]]:
        """
        Constraint propagation (Forward Checking).
        
        Removes conflicting domain values from remaining unassigned courses.
        If any unassigned course domain is reduced to zero valid values,
        signals an early wipeout (returns False) so backtracking occurs immediately.
        """
        pruned_records: Dict[str, List[ScheduleValue]] = {c.id: [] for c in unassigned_courses}

        for other_course in unassigned_courses:
            original_domain = current_domains[other_course.id]
            valid_remaining: List[ScheduleValue] = []

            for val in original_domain:
                consistent, _ = HardConstraintValidator.is_consistent(
                    other_course, val, current_assignments, self.problem
                )
                if consistent:
                    valid_remaining.append(val)
                else:
                    pruned_records[other_course.id].append(val)

            # Early wipeout detection: domain has no consistent assignments
            if not valid_remaining:
                # Restore immediately before returning failure
                self.restore_pruned_domains(current_domains, pruned_records)
                return False, {}

            current_domains[other_course.id] = valid_remaining

        return True, pruned_records

    def restore_pruned_domains(
        self,
        current_domains: Dict[str, List[ScheduleValue]],
        pruned_records: Dict[str, List[ScheduleValue]],
    ):
        """Restore pruned values back into the respective domains upon backtracking."""
        for course_id, pruned_vals in pruned_records.items():
            if course_id in current_domains:
                current_domains[course_id].extend(pruned_vals)

    def _backtrack_search(
        self,
        current_assignments: List[Assignment],
        unassigned_courses: List[Course],
        current_domains: Dict[str, List[ScheduleValue]],
        depth: int = 0,
    ) -> Optional[List[Assignment]]:
        """Recursive backtracking search with MRV, soft-ordering, and forward checking."""
        if not unassigned_courses:
            return current_assignments

        # 1. Select variable using MRV
        selected_course = self.select_unassigned_variable_mrv(
            unassigned_courses, current_domains, current_assignments
        )
        self._log(
            f"[MRV] Selected Course: {selected_course.name} ({selected_course.id}) "
            f"| Remaining unassigned: {len(unassigned_courses)}"
        )

        # 2. Order candidate domain values using soft-constraint utility
        candidate_domain = current_domains.get(selected_course.id, [])
        ordered_values = self.order_domain_values(
            selected_course, candidate_domain, current_assignments
        )

        remaining_courses = [c for c in unassigned_courses if c.id != selected_course.id]

        for val in ordered_values:
            self.assignments_tried += 1
            
            # Check hard constraint consistency
            consistent, reason = HardConstraintValidator.is_consistent(
                selected_course, val, current_assignments, self.problem
            )
            if not consistent:
                self._log(f"  [REJECT] {selected_course.id} -> {val} ({reason})")
                continue

            self._log(f"  [TRY] {selected_course.id} -> {val}")

            # Create assignment
            new_assignment = Assignment(
                course_id=selected_course.id,
                course_name=selected_course.name,
                faculty_id=selected_course.faculty_id,
                student_group_id=selected_course.student_group_id,
                room_id=val.room_id,
                day=val.day,
                start_time=val.start_time,
                duration=selected_course.duration,
                is_lab=selected_course.is_lab,
                enrollment=selected_course.enrollment,
            )
            current_assignments.append(new_assignment)

            # Forward checking / constraint propagation
            success_propagate, pruned_records = self.forward_check_and_prune(
                selected_course, val, remaining_courses, current_domains, current_assignments
            )

            if success_propagate:
                # Recurse
                result = self._backtrack_search(
                    current_assignments, remaining_courses, current_domains, depth + 1
                )
                if result is not None:
                    return result
                
                # Undo forward checking pruning on search branch failure
                self.restore_pruned_domains(current_domains, pruned_records)

            # Backtrack
            self.backtracks += 1
            self._log(f"  [BACKTRACK] Undoing assignment {selected_course.id} -> {val}")
            current_assignments.pop()

        return None

    def solve(self) -> SolverResult:
        """
        Execute the CSP scheduling search.
        
        Returns a SolverResult containing success status, final schedule, conflicts,
        and execution statistics.
        """
        self.start_time = time.perf_counter()
        self.assignments_tried = 0
        self.backtracks = 0
        self.trace_log = []

        # Validate basic problem consistency
        if not self.problem.courses:
            self.end_time = time.perf_counter()
            return SolverResult(
                success=True,
                schedule=[],
                conflicts=[],
                statistics={
                    "variables": 0,
                    "assignments_tried": 0,
                    "backtracks": 0,
                    "search_time_sec": round(self.end_time - self.start_time, 6),
                    "total_utility": 0.0,
                },
            )

        # Generate initial domains
        initial_domains = self.generate_initial_domains()

        # Check for courses with initially empty domains
        empty_domain_courses = [
            c.id for c in self.problem.courses if not initial_domains.get(c.id)
        ]
        if empty_domain_courses:
            self.end_time = time.perf_counter()
            conflicts = [
                f"Course {cid} has no viable domain (incompatible room capacity, lab type, or faculty schedule)."
                for cid in empty_domain_courses
            ]
            return SolverResult(
                success=False,
                schedule=[],
                conflicts=conflicts,
                statistics={
                    "variables": len(self.problem.courses),
                    "assignments_tried": 0,
                    "backtracks": 0,
                    "search_time_sec": round(self.end_time - self.start_time, 6),
                    "total_utility": 0.0,
                },
            )

        # Run Backtracking Search
        schedule_assignments = self._backtrack_search(
            current_assignments=[],
            unassigned_courses=list(self.problem.courses),
            current_domains=initial_domains,
        )

        self.end_time = time.perf_counter()
        search_time = round(self.end_time - self.start_time, 6)

        if schedule_assignments is not None:
            # Calculate total schedule utility
            total_utility = sum(
                SoftConstraintEvaluator.evaluate_assignment_utility(
                    self.problem.get_course(a.course_id),
                    ScheduleValue(a.room_id, a.day, a.start_time),
                    schedule_assignments,
                    self.problem,
                    self.weights,
                )
                for a in schedule_assignments
                if self.problem.get_course(a.course_id)
            )

            # Sort schedule chronologically for readable display
            day_order = {day: idx for idx, day in enumerate(self.problem.days)}
            schedule_dict_list = [a.to_dict() for a in schedule_assignments]
            schedule_dict_list.sort(
                key=lambda x: (
                    day_order.get(x["day"], 99),
                    x["start_time"],
                    x["room_id"],
                )
            )

            return SolverResult(
                success=True,
                schedule=schedule_dict_list,
                conflicts=[],
                statistics={
                    "variables": len(self.problem.courses),
                    "assignments_tried": self.assignments_tried,
                    "backtracks": self.backtracks,
                    "search_time_sec": search_time,
                    "total_utility": round(total_utility, 4),
                },
            )
        else:
            return SolverResult(
                success=False,
                schedule=[],
                conflicts=["CSP search exhausted all branches without finding a conflict-free schedule."],
                statistics={
                    "variables": len(self.problem.courses),
                    "assignments_tried": self.assignments_tried,
                    "backtracks": self.backtracks,
                    "search_time_sec": search_time,
                    "total_utility": 0.0,
                },
            )
