
import pytest

from app import create_app
from database.db import db


@pytest.fixture
def client():
    app = create_app("testing")
    app.config["TESTING"] = True

    with app.app_context():
        db.create_all()

        with app.test_client() as test_client:
            yield test_client

        db.session.remove()


def test_conflicts_endpoint_returns_valid_response(client):
    response = client.get("/api/conflicts")

    assert response.status_code == 200

    data = response.get_json()

    assert data["success"] is True
    assert isinstance(data["count"], int)
    assert isinstance(data["conflicts"], list)


def test_conflicts_endpoint_accepts_timetable_id(client):
    # A missing timetable should be reported as not found.
    response = client.get("/api/conflicts?timetable_id=999999")

    assert response.status_code == 404

    data = response.get_json()
    assert data["success"] is False


def test_conflicts_endpoint_rejects_unknown_timetable(client):
    response = client.get("/api/conflicts?timetable_id=999999")

    assert response.status_code == 404

    data = response.get_json()

    assert data["success"] is False
