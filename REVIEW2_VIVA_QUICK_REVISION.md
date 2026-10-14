# CampusFlow: Review 2 Viva Quick Revision & Master Q&A
**Course:** 23CSE401 — Fundamentals of Artificial Intelligence  
**Project:** College Classroom Scheduling System Using Multi-Agent Systems (MAS)  
**Team:** Group 6 (Arpitha Shri Su, Dhanuja A, Harini N)  

This revision guide provides 20 likely viva questions with concise, technically sound answers to help you answer questions during evaluation.

---

### 1. Fundamentals of Multi-Agent Systems (MAS)

#### Q1: What is a Multi-Agent System (MAS), and why is it preferred over a monolithic centralized scheduler for this problem?
**Answer:**  
A Multi-Agent System consists of multiple autonomous entities (agents) situated in an environment, capable of flexible, autonomous action to meet their design objectives.  
*Why MAS for Timetabling:* In real colleges, scheduling is not a static calculation; it involves distinct stakeholders with private information and conflicting goals (faculty personal schedules, room ownership, department policies, student cohorts). A centralized monolithic solver requires all private constraints to be exposed in a single global matrix. MAS distributes ownership, enables local conflict negotiation (counter-proposals), and provides an auditable, transparent consensus trail that centralized solvers lack.

#### Q2: What is the PEAS framework for the agents in CampusFlow?
**Answer:**  
The PEAS (Performance Measure, Environment, Actuators, Sensors) profile for our five agents is:

| Agent | Performance Measure (P) | Environment (E) | Actuators (A) | Sensors (S) |
| :--- | :--- | :--- | :--- | :--- |
| **DepartmentAgent** | All curriculum course requirements scheduled without quota deficits | Academic semester syllabus, department course lists | Emits `REQUEST` messages to Coordinator | Receives `FINAL_ACCEPT` or `REJECT` replies |
| **FacultyAgent** | Teaching load balance, zero double-booking, adherence to daily/consecutive limits, satisfaction of preferred time slots | Weekly schedule, instructor personal calendar, hourly workload policies | Emits `ACCEPT`, `REJECT`, `COUNTER_PROPOSE` | Receives `PROPOSE`, `CONFIRM`, `CANCEL` |
| **ClassroomAgent** | High seat utilization ratio, zero room double-booking, 100% room-type compatibility (labs for lab courses) | Campus physical rooms and labs, seat capacities, equipment | Emits `ACCEPT`, `REJECT`, `CONFLICT` | Receives `ALLOCATE`, `PROPOSE`, `CONFIRM`, `CANCEL` |
| **StudentGroupAgent** | Zero timetable clashes for student cohort, minimal idle gap hours between lectures, protection of existing commitments | Cohort academic calendar, section commitments | Emits `ACCEPT`, `REJECT`, `CONFLICT` | Receives `CHECK_TIMETABLE`, `CONFIRM`, `CANCEL` |
| **TimetableCoordinatorAgent** | 100% hard-constraint compliance, maximum total schedule utility, minimal negotiation rounds | Complete multi-agent network, CSP domain space, database session | Emits `PROPOSE`, `ALLOCATE`, `CHECK_TIMETABLE`, `CONFIRM`, `CANCEL` | Receives agent votes, rejections, timeouts, and API requests |

---

### 2. Constraint Satisfaction Problem (CSP) & Algorithms

#### Q3: Formally define the Constraint Satisfaction Problem (CSP) in CampusFlow.
**Answer:**  
A CSP is formally defined by the triad $(X, D, C)$:
- **Variables ($X$):** The set of courses to be scheduled: $X = \{C_1, C_2, \dots, C_n\}$.
- **Domains ($D$):** For each course $C_i$, its domain $D_i$ is the set of legal candidate assignments: $D_i = \{(r, d, t) \mid r \in \text{Rooms}, d \in \text{Days}, t \in \text{TimeSlots}\}$.
- **Constraints ($C$):** The set of hard constraints $C = \{H_1, H_2, \dots, H_8\}$ specifying allowed combinations of values.

#### Q4: What is the Minimum Remaining Values (MRV) heuristic and why is it used?
**Answer:**  
MRV (also known as the "Most Constrained Variable" or "Fail-First" heuristic) chooses the unassigned course with the fewest remaining legal domain values.  
*Why it works:* By picking the most constrained variable first, we detect dead ends as high up in the search tree as possible, drastically pruning the search space and minimizing wasteful backtracking. In our implementation, ties are broken by longest duration (e.g. 2-hour labs) followed by highest student enrollment.

#### Q5: How does Forward Checking work and what is "Domain Wipeout"?
**Answer:**  
Whenever a variable $X$ is assigned a value $v$:
1. Forward checking looks ahead at all remaining unassigned variables $Y$ connected to $X$ by constraints.
2. It removes from $D_Y$ any value that conflicts with $(X = v)$.
3. **Domain Wipeout:** If any unassigned variable's domain becomes empty ($|D_Y| = 0$), the solver immediately halts that branch and backtracks without exploring useless deeper levels.

#### Q6: What is the difference between simple Backtracking and Backtracking with Forward Checking?
**Answer:**  
- **Simple Backtracking:** Assigns values one by one and only checks constraint consistency *after* assignment. It frequently explores deep branches where an unassigned future variable has already become impossible to schedule.
- **Backtracking with Forward Checking:** Interleaves search with constraint propagation. It maintains the legal domain of every unassigned variable, detects future dead ends immediately (early wipeout), and restores pruned domains when undoing a step.

#### Q7: List and explain the 8 Hard Constraints ($H_1$ to $H_8$) in your project.
**Answer:**  
1. **$H_1$ — Faculty Double-Booking:** An instructor cannot teach two courses simultaneously.
2. **$H_2$ — Classroom Double-Booking:** A room cannot host two classes simultaneously.
3. **$H_3$ — Classroom Capacity:** Room capacity must be greater than or equal to course enrollment ($Capacity \ge Enrollment$).
4. **$H_4$ — Room Type Matching:** A laboratory course must be assigned to a lab room; standard lecture rooms are invalid.
5. **$H_5$ — Faculty Availability:** A course cannot be scheduled when the assigned faculty member is unavailable.
6. **$H_6$ — Student Group Clash:** A student cohort cannot have two classes scheduled in the same time slot, nor during prior commitments.
7. **$H_7$ — Timetable Slot Boundaries:** Classes must start at valid timetable boundaries (09:00 to 16:00).
8. **$H_8$ — Duration Consistency:** Multi-hour courses (e.g., 2-hour labs) must occupy consecutive hours on the same day without spilling past the end of the day.

#### Q8: What soft constraints ($S_1$ to $S_4$) are evaluated, and how are they scored?
**Answer:**  
Soft constraints represent preferences rather than mandatory rules:
- **$S_1$ — Faculty Preference Score:** $1.0$ if the slot matches instructor's preferred hours, $0.0$ otherwise.
- **$S_2$ — Student Gap Minimization:** Penalizes isolated 1–2 hour gaps between classes for the same cohort on the same day.
- **$S_3$ — Room Utilization Efficiency:** Measures $Enrollment / Capacity$, rewarding efficient room sizing and penalizing scheduling small groups in massive auditoriums.
- **$S_4$ — Multi-Criteria Utility Function:**
  $$U = w_1 S_1 + w_2 S_3 + w_3 (1.0 - S_{2,\text{penalty}}) - w_4 S_{2,\text{penalty}}$$
  Candidate domain values are ordered descending by utility score so that the highest-quality slots are evaluated first.

---

### 3. Agent Communication & Negotiation Protocol

#### Q9: What communication protocols and performatives do your agents use?
**Answer:**  
Our agents use standardized FIPA-ACL (Agent Communication Language) performatives serialized as structured JSON bodies over SPADE:
- `REQUEST`: Sent by `DepartmentAgent` to trigger scheduling.
- `PROPOSE`: Sent by `TimetableCoordinatorAgent` to specialist agents with a candidate slot.
- `ALLOCATE`: Sent to `ClassroomAgent` to request room reservation.
- `CHECK_TIMETABLE`: Sent to `StudentGroupAgent` to verify cohort schedule availability.
- `ACCEPT`: Sent by specialist agents when the proposal satisfies local constraints.
- `REJECT`: Sent by specialist agents when a constraint is violated (e.g., capacity insufficient).
- `COUNTER_PROPOSE`: Sent by `FacultyAgent` along with a list of alternative free slots.
- `CONFLICT`: Sent by `ClassroomAgent` or `StudentGroupAgent` when an overlap occurs.
- `RESCHEDULE`: Internal event triggering CSP alternative candidate search.
- `CONFIRM`: Two-phase commit message to finalize provisional bookings.
- `CANCEL`: Compensation message to release provisional reservations upon failure.
- `FINAL_ACCEPT`: Confirmation sent back to `DepartmentAgent` once full consensus is reached.

#### Q10: How do you prevent agents from accepting outdated, duplicated, or unrelated messages?
**Answer:**  
Every outgoing message carries a unique UUID `correlation_id` (set in both the JSON payload and the SPADE `thread` metadata). The coordinator registers an asynchronous future in `self._pending_replies[correlation_id]`.  
When a response arrives, the coordinator validates that:
1. `msg.thread == correlation_id`
2. `msg.sender` matches the registered bare JID of the intended agent.  
If any condition fails, the message is flagged as `UNMATCHED` in the audit log and discarded.

#### Q11: Explain Two-Phase Confirmation and Rollback Compensation in your project.
**Answer:**  
- **Phase 1 (Provisional Negotiation):** The coordinator queries the agents sequentially. Agents check local availability and reply with `ACCEPT`. No permanent reservation is made yet.
- **Phase 2 (Two-Phase Commit):** If all agents accept, the coordinator sends `CONFIRM` to commit the slot locally.
- **Compensation Rollback:** If an agent rejects during Phase 1, or if a network/state failure occurs during Phase 2, the coordinator calls `_cancel_confirmed_targets()`. This transmits `CANCEL` performatives to any agents that already approved the slot, ensuring no orphaned or partial reservations remain in memory.

---

### 4. Database, API & Architecture

#### Q12: How does the system guarantee database consistency if scheduling fails halfway through?
**Answer:**  
All database persistence in `POST /api/schedule/generate` is wrapped in an atomic SQLAlchemy session transaction. Timetable and Assignment records are only flushed and committed after all courses have achieved consensus across all agents. If a negotiation fails or an exception is raised, `db.session.rollback()` is executed immediately, leaving the database unchanged. The failure outcome is recorded in a separate isolated transaction in `AgentAuditLog`.

#### Q13: What REST API endpoints exist in CampusFlow and what HTTP status codes do they return?
**Answer:**  
- `GET /` $\rightarrow$ 200 OK (CampusFlow web UI).
- `GET /api/health` $\rightarrow$ 200 OK (API status check).
- `GET /api/timetables` and `GET /api/timetables/<id>` $\rightarrow$ 200 OK (Timetable retrieval).
- `POST /api/schedule/generate` $\rightarrow$ 201 Created on success; 409 Conflict if infeasible; 400 Bad Request on invalid input.
- `POST /api/schedule/reschedule` $\rightarrow$ 200 OK (Returns alternative candidate slot with utility score).
- `GET /api/conflicts` $\rightarrow$ 200 OK (Returns independent conflict validation report).
- `GET /api/agent-logs` $\rightarrow$ 200 OK (Returns multi-agent audit trail).

#### Q14: How does the Conflict Detection API work independently from the scheduler?
**Answer:**  
The `GET /api/conflicts` endpoint in `api/routes.py` performs a zero-trust audit directly on the persisted database records. It converts time strings to minute intervals, computes durations, and executes an $O(n^2)$ pairwise overlap check for:
1. Shared classroom double-booking
2. Shared faculty double-booking
3. Shared student-group double-booking
4. Classroom capacity violations ($Enrollment > Room.Capacity$)  
This ensures timetable validity is independently proven rather than blindly trusting the solver.

---

### 5. SPADE, XMPP & Engineering Reality

#### Q15: What is SPADE and how is it structured?
**Answer:**  
SPADE (Smart Python Agent Development Environment) is a multi-agent framework built on Python's `asyncio` and the XMPP protocol. It implements the BDI (Belief-Desire-Intention) paradigm and provides event-driven agent behaviours:
- `CyclicBehaviour`: Executes repeatedly in an event loop (e.g. message polling).
- `OneShotBehaviour`: Executes exactly once (e.g. sending a single request).
- `PeriodicBehaviour`: Runs at set time intervals.

#### Q16: What is the difference between In-Process Mode and Live XMPP Mode in your project?
**Answer:**  
- **In-Process Mode (`MAS_LIVE_XMPP=false` - Default):** Agents run in the application runtime. Messages are formatted with full FIPA JSON bodies, performatives, and correlation IDs, and are delivered directly between agent message queues. It requires no network sockets or external servers and is 100% deterministic.
- **Live XMPP Mode (`MAS_LIVE_XMPP=true`):** Agents call `agent.start(auto_register=True)`, connect via TCP sockets to port 5222 using `slixmpp_multiplatform`, and exchange XML stanzas over an XMPP server daemon.

#### Q17: Why does Live XMPP fail against embedded `pyjabber` in your environment?
**Answer:**  
SPADE 4.1.2 uses `slixmpp_multiplatform 1.12.0`. On Python 3.14 on Windows, `slixmpp` attempts an XMPP handshake that falls back to legacy XMPP 0.9 stream headers (`Legacy XMPP 0.9 protocol detected`). The bundled Python XMPP server (`pyjabber 0.4.5`) cannot parse this legacy stream header and logs `"sent unparsable data"`, causing a `DisconnectedException`.  
*Resolution:* For enterprise network deployment, an RFC-compliant server like Prosody or ejabberd is required; for our academic review, the verified in-process mode provides 100% of the MAS logic without socket instability.

---

### 6. Complexity, Testing & Scalability

#### Q18: What is the computational complexity of the scheduling algorithm?
**Answer:**  
- **Worst-case complexity:** $O(d^n)$, where $n$ is the number of courses (variables) and $d$ is the number of candidate slot-room pairs (domain size $\approx 5 \times 8 \times |\text{Rooms}|$).
- **Practical complexity with MRV and Forward Checking:** $O(n \cdot d)$. By applying MRV to choose the most constrained variable first and Forward Checking to prune conflicting domain values immediately, the solver avoids exploring dead-end subtrees. In our tests, 4 courses across 3 rooms solve in under 1 millisecond.

#### Q19: How is the automated test suite structured?
**Answer:**  
The test suite consists of **98 tests** across 16 files:
- **Unit Tests:** `test_base_agent.py`, `test_faculty_agent.py`, `test_classroom_agent.py`, `test_student_group_agent.py`, `test_coordinator_agent.py`.
- **Constraint Tests:** `test_csp_solver.py` explicitly tests every constraint ($H_1$ to $H_8$) individually.
- **API Tests:** `test_api.py` and `test_conflict_detection.py` test all REST endpoints.
- **Integration Tests:** `test_integration.py` and `test_mas_scheduling_service.py` test end-to-end service orchestration and transaction rollbacks.
- **Results:** 97 pass in 2.2 seconds; 1 is skipped (opt-in external XMPP test).

#### Q20: What are the main limitations of the current implementation and how would you scale it?
**Answer:**  
1. **Network XMPP Cluster:** Replace embedded `pyjabber` with a containerized Prosody XMPP cluster to enable multi-server deployment across university campuses.
2. **Dynamic Real-Time Re-negotiation:** When a professor falls ill during the semester, trigger an automated push notification via WebSocket to student phones offering rescheduling alternatives.
3. **Advanced Soft Constraint Tuning:** Allow academic deans to interactively adjust the utility weights ($w_1, w_2, w_3$) on the CampusFlow frontend to prioritize either student convenience or room efficiency.
