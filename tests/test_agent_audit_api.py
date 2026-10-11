import pytest

from app import create_app
from app.models import AgentAuditLog
from database.db import db
from agents.communication import AgentMessageLogger


@pytest.fixture
def app():
    app = create_app("testing")

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_agent_message_is_persisted_to_database(app):
    with app.app_context():
        logger = AgentMessageLogger()

        logger.log_message(
            sender="faculty@localhost",
            receiver="coordinator@localhost",
            message_type="PROPOSE",
            course="CS301",
            payload={"course_id": "CS301", "day": "Monday"},
            status="SENT",
        )

        record = AgentAuditLog.query.filter_by(
            message_type="PROPOSE"
        ).first()

        assert record is not None
        assert record.sender == "faculty@localhost"
        assert record.course_id == "CS301"
        assert record.payload["day"] == "Monday"


def test_agent_logs_api_returns_persisted_records(app):
    with app.app_context():
        record = AgentAuditLog(
            timestamp="10:30:00",
            sender="faculty@localhost",
            receiver="coordinator@localhost",
            message_type="PROPOSE",
            course_id="CS301",
            status="SENT",
        )
        record.payload = {"course_id": "CS301"}
        db.session.add(record)
        db.session.commit()

    response = app.test_client().get("/api/agent-logs")

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] == 1
    assert data["logs"][0]["course_id"] == "CS301"