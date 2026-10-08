"""Unit tests for BaseAgent class."""

import pytest
import asyncio
from agents.base_agent import BaseAgent
from agents.communication import PROPOSE, ACCEPT


def test_base_agent_initialization():
    """Verify BaseAgent identity, name extraction, and default configuration."""
    agent = BaseAgent(
        jid="test_agent@localhost",
        password="test_password",
        role="TestWorker",
    )
    assert agent.agent_name == "test_agent"
    assert agent.role == "TestWorker"
    assert str(agent.jid) == "test_agent@localhost"
    assert agent.message_history == []


def test_base_agent_make_message():
    """Verify message building helper."""
    agent = BaseAgent(jid="sender@localhost")
    msg = agent.make_message(
        to="receiver@localhost",
        performative=PROPOSE,
        payload={"course_id": "CS101", "day": "Monday", "start_time": "09:00"},
    )
    assert str(msg.to) == "receiver@localhost"
    assert str(msg.sender) == "sender@localhost"
    assert msg.get_metadata("performative") == PROPOSE


def test_base_agent_communication_logging():
    """Verify that communication logging records messages in history."""
    agent = BaseAgent(jid="my_agent@localhost", role="CustomRole")
    entry = agent.log_communication(
        direction="SENT",
        sender="my_agent@localhost",
        receiver="other_agent@localhost",
        performative=PROPOSE,
        payload={"course_id": "CS102"},
        status="OK",
    )
    assert len(agent.message_history) == 1
    assert entry["sender"] == "my_agent@localhost"
    assert entry["receiver"] == "other_agent@localhost"
    assert entry["message_type"] == PROPOSE


def test_base_agent_lifecycle():
    """Test setup and stop lifecycle execution."""
    agent = BaseAgent(jid="lifecycle_agent@localhost")

    async def run_lifecycle():
        await agent.setup()
        assert agent._is_running is True
        await agent.stop()
        assert agent._is_running is False

    asyncio.run(run_lifecycle())
