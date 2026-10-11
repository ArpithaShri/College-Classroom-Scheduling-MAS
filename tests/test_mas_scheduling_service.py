
from types import SimpleNamespace

import pytest

import services.mas_scheduling_service as mas_service


# ---------------------------------------------------------
# Fake scheduler
# ---------------------------------------------------------

class FakeScheduler:
    success = True
    schedule = [
        {
            "course_id": "C1",
            "room_id": "R1",
            "day": "Monday",
            "start_time": "09:00",
        }
    ]

    def __init__(self, problem, enable_logging=False):
        self.problem = problem

    def solve(self):
        return SimpleNamespace(
            success=FakeScheduler.success,
            schedule=FakeScheduler.schedule,
            statistics={"scheduled": len(FakeScheduler.schedule)},
        )


# ---------------------------------------------------------
# Fake agents
# ---------------------------------------------------------

class FakeAgent:
    stopped = []
    fail_start = False

    def __init__(self, jid, password=None, **kwargs):
        self.jid = jid
        self.password = password
        self.kwargs = kwargs

    async def start(self, auto_register=True):
        if FakeAgent.fail_start:
            raise RuntimeError("Simulated startup failure")

    async def stop(self):
        FakeAgent.stopped.append(str(self.jid))


class FakeCoordinator(FakeAgent):
    negotiation_success = True

    def __init__(self, jid, password=None, scheduling_problem=None, **kwargs):
        super().__init__(jid, password, **kwargs)
        self.scheduling_problem = scheduling_problem

    def register_faculty_agent(self, faculty_id, jid):
        pass

    def register_classroom_agent(self, room_id, jid):
        pass

    def register_student_group_agent(self, group_id, jid):
        pass

    async def coordinate_course_negotiation(
        self, request_payload, **kwargs
    ):
        # **kwargs allows both offline and live-mode service calls.
        if FakeCoordinator.negotiation_success:
            return True, request_payload, None

        return False, None, "Negotiation rejected"


# ---------------------------------------------------------
# Test data
# ---------------------------------------------------------

def make_problem():
    faculty = [
        SimpleNamespace(
            id="F1",
            name="Faculty One",
            available_slots=None,
            preferred_slots=None,
            max_daily_hours=6,
            max_consecutive_hours=3,
        )
    ]

    rooms = [
        SimpleNamespace(
            id="R1",
            name="Room One",
            capacity=60,
            room_type="classroom",
            available_slots=None,
        )
    ]

    student_groups = [
        SimpleNamespace(
            id="G1",
            name="Group One",
            size=40,
            commitments=None,
        )
    ]

    course = SimpleNamespace(
        id="C1",
        name="Course One",
        faculty_id="F1",
        student_group_id="G1",
        enrollment=40,
        duration=1,
        is_lab=False,
    )

    return SimpleNamespace(
        faculty=faculty,
        rooms=rooms,
        student_groups=student_groups,
        get_course=lambda course_id: (
            course if course_id == "C1" else None
        ),
    )


# ---------------------------------------------------------
# Test setup
# ---------------------------------------------------------

@pytest.fixture(autouse=True)
def configure_fakes(monkeypatch):
    FakeScheduler.success = True
    FakeScheduler.schedule = [
        {
            "course_id": "C1",
            "room_id": "R1",
            "day": "Monday",
            "start_time": "09:00",
        }
    ]

    FakeAgent.stopped = []
    FakeAgent.fail_start = False
    FakeCoordinator.negotiation_success = True

    monkeypatch.setattr(
        mas_service, "CSPScheduler", FakeScheduler
    )
    monkeypatch.setattr(
        mas_service, "FacultyAgent", FakeAgent
    )
    monkeypatch.setattr(
        mas_service, "ClassroomAgent", FakeAgent
    )
    monkeypatch.setattr(
        mas_service, "StudentGroupAgent", FakeAgent
    )
    monkeypatch.setattr(
        mas_service, "TimetableCoordinatorAgent", FakeCoordinator
    )


# ---------------------------------------------------------
# Tests
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_in_process_schedule_returns_confirmed_assignments():
    service = mas_service.MASTimetableService(
        make_problem(),
    )

    result = await service.schedule()

    assert result["success"] is True
    assert len(result["assignments"]) == 1
    assert result["assignments"][0]["course_id"] == "C1"
    assert result["agent_count"] == 4
    assert result["negotiated_count"] == 1
    assert result["mode"] == "in_process"

    # In-process agents are not started as SPADE/XMPP processes.
    assert FakeAgent.stopped == []


@pytest.mark.asyncio
async def test_schedule_fails_when_csp_is_infeasible():
    FakeScheduler.success = False

    service = mas_service.MASTimetableService(make_problem())

    with pytest.raises(
        mas_service.MASSchedulingError,
        match="CSP scheduler could not find",
    ):
        await service.schedule()


@pytest.mark.asyncio
async def test_schedule_fails_when_negotiation_is_rejected():
    FakeCoordinator.negotiation_success = False

    service = mas_service.MASTimetableService(make_problem())

    with pytest.raises(
        mas_service.MASSchedulingError,
        match="Negotiation failed",
    ):
        await service.schedule()

    assert FakeAgent.stopped == []


@pytest.mark.asyncio
async def test_fake_live_schedule_stops_all_agents_after_success():
    service = mas_service.MASTimetableService(
        make_problem(),
        live_xmpp=True,
    )

    result = await service.schedule()

    assert result["mode"] == "live_xmpp"
    assert len(FakeAgent.stopped) == 4
    assert len(set(FakeAgent.stopped)) == 4


@pytest.mark.asyncio
async def test_fake_live_negotiation_failure_stops_started_agents():
    FakeCoordinator.negotiation_success = False
    service = mas_service.MASTimetableService(
        make_problem(),
        live_xmpp=True,
    )

    with pytest.raises(
        mas_service.MASSchedulingError,
        match="Negotiation failed",
    ):
        await service.schedule()

    assert len(FakeAgent.stopped) == 4
    assert len(set(FakeAgent.stopped)) == 4


@pytest.mark.asyncio
async def test_schedule_stops_started_agents_if_startup_fails(
    monkeypatch,
):
    class FailingClassroomAgent(FakeAgent):
        async def start(self, auto_register=True):
            if str(self.jid).startswith("classroom_"):
                raise RuntimeError("Simulated startup failure")

            await super().start(auto_register=auto_register)

    monkeypatch.setattr(
        mas_service, "FacultyAgent", FailingClassroomAgent
    )
    monkeypatch.setattr(
        mas_service, "ClassroomAgent", FailingClassroomAgent
    )
    monkeypatch.setattr(
        mas_service, "StudentGroupAgent", FailingClassroomAgent
    )

    service = mas_service.MASTimetableService(
        make_problem(),
        live_xmpp=True,
    )

    with pytest.raises(
        mas_service.MASSchedulingError,
        match="Could not start SPADE agent",
    ):
        await service.schedule()

    # The faculty agent starts first. When classroom startup fails,
    # the already-started faculty agent must be stopped.
    assert len(FakeAgent.stopped) == 1
    assert FakeAgent.stopped[0].startswith("faculty_")
