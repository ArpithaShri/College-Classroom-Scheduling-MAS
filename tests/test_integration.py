"""Integration tests for scheduling API, database persistence, and rollback."""

import pytest

from app import create_app
from app.models import Assignment, Timetable
from database.db import db
from database.seed_data import seed_database
from sqlalchemy.orm import Session


@pytest.fixture
def integration_app():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        seed_database()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(integration_app):
    return integration_app.test_client()


def test_generated_timetable_is_persisted_and_retrievable(client):
    response = client.post(
        "/api/schedule/generate",
        json={"name": "Integration Test Timetable", "academic_term": "Fall 2026"},
    )

    assert response.status_code == 201
    result = response.get_json()
    assert result["success"] is True

    timetable_id = result["timetable_id"]

    with client.application.app_context():
        timetable = db.session.get(Timetable, timetable_id)
        assert timetable is not None
        assert timetable.name == "Integration Test Timetable"
        assert timetable.status == "SCHEDULED"
        assert len(timetable.assignments) == len(result["assignments"])
        assert len(timetable.assignments) > 0

    retrieved = client.get(f"/api/timetable/{timetable_id}")
    assert retrieved.status_code == 200
    assert retrieved.get_json()["timetable"]["id"] == timetable_id


def test_failed_timetable_commit_rolls_back_database_changes(
    client, integration_app, monkeypatch
):
    def fail_commit(self):
        raise RuntimeError("Simulated database commit failure")

    with integration_app.app_context():
        original_count = Timetable.query.count()
        monkeypatch.setattr(Session, "commit", fail_commit)

        response = client.post(
            "/api/schedule/generate",
            json={"name": "Must Roll Back"},
        )

        assert response.status_code == 500
        assert response.get_json()["success"] is False

        # The endpoint must roll back the partially created timetable.
        assert Timetable.query.count() == original_count
        assert Timetable.query.filter_by(name="Must Roll Back").first() is None


def test_reschedule_proposal_does_not_silently_change_existing_assignment(client):
    generated = client.post("/api/schedule/generate", json={})
    assert generated.status_code == 201

    result = generated.get_json()
    timetable_id = result["timetable_id"]
    original = next(
        item for item in result["assignments"] if item["course_id"] == "CS301"
    )

    response = client.post(
        "/api/schedule/reschedule",
        json={
            "course_id": "CS301",
            "timetable_id": timetable_id,
            "current_room_id": original["room_id"],
            "current_day": original["day"],
            "current_time": original["start_time"],
        },
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True

    with client.application.app_context():
        assignment = Assignment.query.filter_by(
            timetable_id=timetable_id,
            course_id="CS301",
        ).first()

        assert assignment is not None
        assert assignment.room_id == original["room_id"]
        assert assignment.day == original["day"]
        assert assignment.start_time == original["start_time"]
