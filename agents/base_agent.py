
"""Base Agent implementation for SPADE Multi-Agent System.

Provides common initialization, structured logging, message construction helpers,
lifecycle hooks, and safe shutdown without domain-specific scheduling logic.
"""

import logging
import uuid
from typing import Optional, Dict, Any, Union, List, Tuple

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
        super().__init__(
            jid=str(jid),
            password=pwd,
            verify_security=verify_security,
        )

        self.role = role
        self.agent_name = str(jid).split("@")[0]
        self.message_history: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(
            f"agents.{self.role}.{self.agent_name}"
        )
        self._is_running = False

    async def setup(self):
        """Lifecycle hook invoked upon agent startup."""
        self._is_running = True
        self.logger.info(
            "Agent %s (%s) initialized and ready.",
            self.agent_name,
            self.role,
        )

    async def stop(self):
        """Lifecycle hook invoked upon agent shutdown."""
        self._is_running = False
        self.logger.info(
            "Agent %s (%s) stopping...",
            self.agent_name,
            self.role,
        )
        await super().stop()

    def make_message(
        self,
        to: str,
        performative: str,
        payload: Optional[
            Union[Dict[str, Any], SchedulingMessagePayload]
        ] = None,
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
            status=(
                f"{direction.upper()}:{status}"
                if status
                else direction.upper()
            ),
            reason=reason or (
                payload.get("reason") if payload else None
            ),
        )

        self.message_history.append(entry)
        return entry

    async def send_message(
        self,
        to: str,
        performative: str,
        payload: Optional[
            Union[Dict[str, Any], SchedulingMessagePayload]
        ] = None,
        thread: Optional[str] = None,
        behavior: Any = None,
    ) -> Message:
        """Send a message using the live SPADE behavior that owns transport."""
        if behavior is None or getattr(behavior, "agent", None) is not self:
            raise RuntimeError(
                "A running SPADE behavior is required to send a live message."
            )
        if not self.is_alive():
            raise RuntimeError("Cannot send a live message from a stopped agent.")

        if isinstance(payload, dict):
            payload = dict(payload)
            payload.setdefault("correlation_id", str(uuid.uuid4()))
            thread = thread or payload["correlation_id"]

        msg = self.make_message(
            to=to,
            performative=performative,
            payload=payload,
            thread=thread,
        )

        _, parsed_payload = parse_spade_message(msg)
        self.log_communication(
            direction="SENT",
            sender=str(self.jid),
            receiver=str(to),
            performative=performative,
            payload=parsed_payload,
            status="ATTEMPTED",
        )

        try:
            await behavior.send(msg)
        except Exception as exc:
            self.log_communication(
                direction="SENT",
                sender=str(self.jid),
                receiver=str(to),
                performative=performative,
                payload=parsed_payload,
                status="FAILED",
                reason=str(exc),
            )
            raise

        self.log_communication(
            direction="SENT",
            sender=str(self.jid),
            receiver=str(to),
            performative=performative,
            payload=parsed_payload,
            status="TRANSMITTED",
        )

        return msg

    async def send_reply(
        self, behavior: Any, msg: Message
    ) -> None:
        """Send an agent reply and record transport outcomes accurately."""
        if behavior is None or getattr(behavior, "agent", None) is not self:
            raise RuntimeError(
                "A running SPADE behavior is required to send a live reply."
            )
        if not self.is_alive():
            raise RuntimeError("Cannot send a live reply from a stopped agent.")

        performative, payload = parse_spade_message(msg)
        sender = str(self.jid)
        receiver = str(msg.to)

        self.log_communication(
            direction="SENT",
            sender=sender,
            receiver=receiver,
            performative=performative,
            payload=payload,
            status="ATTEMPTED",
        )
        try:
            await behavior.send(msg)
        except Exception as exc:
            self.log_communication(
                direction="SENT",
                sender=sender,
                receiver=receiver,
                performative=performative,
                payload=payload,
                status="FAILED",
                reason=str(exc),
            )
            raise

        self.log_communication(
            direction="SENT",
            sender=sender,
            receiver=receiver,
            performative=performative,
            payload=payload,
            status="TRANSMITTED",
        )

    def record_received_message(
        self, msg: Message, simulated: bool = False
    ) -> Tuple[str, Dict[str, Any]]:
        """Parse and log an incoming SPADE message."""
        performative, payload = parse_spade_message(msg)

        self.log_communication(
            direction="SIMULATED" if simulated else "LIVE",
            sender=str(msg.sender or "UNKNOWN"),
            receiver=str(self.jid),
            performative=performative,
            payload=payload,
            status="RECEIVED",
            reason=payload.get("reason"),
        )

        return performative, payload
