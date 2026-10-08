"""Base Agent implementation for SPADE Multi-Agent System.

Provides common initialization, structured logging, message construction helpers,
lifecycle hooks, and safe shutdown without domain-specific scheduling logic.
"""

import logging
from typing import Optional, Dict, Any, Union, List

from spade.agent import Agent
from spade.message import Message

from config import Config
from .communication import (
    create_spade_message,
    parse_spade_message,
    agent_logger,
    SchedulingMessagePayload,
)


class BaseAgent(Agent):
    """Reusable base agent for all SPADE agents in the classroom scheduling system."""

    def __init__(
        self,
        jid: str,
        password: Optional[str] = None,
        verify_security: bool = False,
        role: str = "BaseAgent",
        **kwargs,
    ):
        pwd = password if password is not None else Config.XMPP_PASSWORD
        super().__init__(jid=str(jid), password=pwd, verify_security=verify_security)

        self.role = role
        self.agent_name = str(jid).split("@")[0]
        self.message_history: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(f"agents.{self.role}.{self.agent_name}")
        self._is_running = False

    async def setup(self):
        """Lifecycle hook invoked upon agent startup."""
        self._is_running = True
        self.logger.info(f"Agent {self.agent_name} ({self.role}) initialized and ready.")

    async def stop(self):
        """Lifecycle hook invoked upon agent shutdown."""
        self._is_running = False
        self.logger.info(f"Agent {self.agent_name} ({self.role}) stopping...")
        await super().stop()

    def make_message(
        self,
        to: str,
        performative: str,
        payload: Optional[Union[Dict[str, Any], SchedulingMessagePayload]] = None,
        thread: Optional[str] = None,
    ) -> Message:
        """Construct a standardized SPADE Message targeting another agent."""
        return create_spade_message(
            to=to,
            sender=str(self.jid),
            performative=performative,
            payload=payload,
            thread=thread,
        )

    def log_communication(
        self,
        direction: str,
        sender: str,
        receiver: str,
        performative: str,
        payload: Optional[Dict[str, Any]] = None,
        status: str = "",
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record an outgoing or incoming communication entry."""
        course_id = payload.get("course_id", "") if payload else ""
        entry = agent_logger.log_message(
            sender=sender,
            receiver=receiver,
            message_type=performative,
            course=course_id,
            payload=payload,
            status=f"{direction.upper()}:{status}" if status else direction.upper(),
            reason=reason or (payload.get("reason") if payload else None),
        )
        self.message_history.append(entry)
        return entry

    async def send_message(
        self,
        to: str,
        performative: str,
        payload: Optional[Union[Dict[str, Any], SchedulingMessagePayload]] = None,
        thread: Optional[str] = None,
    ) -> Message:
        """Create, log, and asynchronously transmit a SPADE message."""
        msg = self.make_message(
            to=to, performative=performative, payload=payload, thread=thread
        )
        _, parsed_payload = parse_spade_message(msg)

        self.log_communication(
            direction="SENT",
            sender=str(self.jid),
            receiver=str(to),
            performative=performative,
            payload=parsed_payload,
        )

        try:
            # Check if presence or client connection is active
            if hasattr(self, "client") and self.client and hasattr(self.client, "send"):
                await self.send(msg)
        except Exception as e:
            self.logger.debug(f"Direct spade send encountered: {e}")

        return msg

    def record_received_message(
        self, msg: Message
    ) -> Tuple[str, Dict[str, Any]]:
        """Parse and log an incoming SPADE message."""
        performative, payload = parse_spade_message(msg)
        self.log_communication(
            direction="RECEIVED",
            sender=str(msg.sender or "UNKNOWN"),
            receiver=str(self.jid),
            performative=performative,
            payload=payload,
            reason=payload.get("reason"),
        )
        return performative, payload
