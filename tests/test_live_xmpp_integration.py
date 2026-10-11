"""Opt-in integration tests requiring a real XMPP server and SPADE accounts."""

import asyncio
import os

import pytest

from scheduler.domain import (
    Course,
    Faculty,
    Room,
    SchedulingProblem,
    StudentGroup,
)
from services.mas_scheduling_service import generate_timetable_with_mas


LIVE_XMPP_CONFIGURED = (
    os.environ.get("MAS_XMPP_INTEGRATION", "").strip().lower()
    in {"1", "true", "yes", "on"}
    and bool(os.environ.get("XMPP_DOMAIN"))
    and bool(os.environ.get("XMPP_PASSWORD"))
)


@pytest.mark.skipif(
    not LIVE_XMPP_CONFIGURED,
    reason=(
        "Set MAS_XMPP_INTEGRATION=1, XMPP_DOMAIN, and XMPP_PASSWORD "
        "to run against an actual XMPP server."
    ),
)
def test_live_spade_agents_complete_correlated_negotiation():
    problem = SchedulingProblem(
        courses=[
            Course(
                id="LIVE-C1",
                name="Live integration course",
                faculty_id="LIVE-F1",
                student_group_id="LIVE-G1",
                enrollment=20,
            )
        ],
        faculty=[Faculty(id="LIVE-F1", name="Live faculty")],
        rooms=[
            Room(
                id="LIVE-R1",
                name="Live classroom",
                capacity=30,
            )
        ],
        student_groups=[
            StudentGroup(id="LIVE-G1", name="Live group")
        ],
    )

    result = asyncio.run(
        generate_timetable_with_mas(
            problem,
            password=os.environ["XMPP_PASSWORD"],
            xmpp_domain=os.environ["XMPP_DOMAIN"],
            live_xmpp=True,
        )
    )

    assert result["mode"] == "live_xmpp"
    assert result["negotiated_count"] == 1
    assert result["assignments"][0]["status"] == "SCHEDULED"
