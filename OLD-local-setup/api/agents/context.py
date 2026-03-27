"""
Extended AgentContext — shared state that flows through the entire agentic migration pipeline.

Extends the concept from ``backend.migrator.llm_agent.AgentContext`` with:
  - UUID-based tracking
  - Per-agent execution traces and token accounting
  - Artifact storage for intermediate outputs
  - Inter-agent message passing
  - Full execution-trace serialisation for persistence / debugging
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

import structlog

# Re-export the original context so callers can reach it via this module
from backend.migrator.llm_agent import AgentContext as _LegacyAgentContext

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
#  Supporting data-classes
# ---------------------------------------------------------------------------

@dataclass
class AgentTrace:
    """Execution record for a single agent run."""

    agent_name: str
    status: Literal["pending", "running", "success", "partial", "error", "timeout", "skipped"] = "pending"
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    duration_ms: int = 0
    token_usage: int = 0
    error: Optional[str] = None
    retries: int = 0
    rag_queries: List[str] = field(default_factory=list)
    rag_results_used: int = 0
    fallback_used: bool = False

    def mark_started(self) -> None:
        self.status = "running"
        self.started_at = time.monotonic()

    def mark_finished(
        self,
        status: str,
        token_usage: int = 0,
        error: Optional[str] = None,
        fallback_used: bool = False,
    ) -> None:
        self.finished_at = time.monotonic()
        self.status = status  # type: ignore[assignment]
        self.token_usage = token_usage
        self.error = error
        self.fallback_used = fallback_used
        if self.started_at is not None:
            self.duration_ms = int((self.finished_at - self.started_at) * 1000)

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "token_usage": self.token_usage,
            "error": self.error,
            "retries": self.retries,
            "rag_queries": self.rag_queries,
            "rag_results_used": self.rag_results_used,
            "fallback_used": self.fallback_used,
        }


@dataclass
class AgentMessage:
    """A message exchanged between agents through the shared context."""

    sender: str
    receiver: str  # "*" means broadcast
    content: Any
    timestamp: float = field(default_factory=time.time)
    msg_type: str = "info"  # info | warning | request | response

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "timestamp": self.timestamp,
            "msg_type": self.msg_type,
        }


# ---------------------------------------------------------------------------
#  Extended AgentContext
# ---------------------------------------------------------------------------

class AgentContext(_LegacyAgentContext):
    """Extended pipeline context carrying state across all agents.

    Inherits from the legacy ``AgentContext`` so that existing migrator
    functions (``convert_unknown_element``, etc.) continue to work
    unchanged — they only see the ``enabled``, ``llm_config``,
    ``conversions``, and ``skipped`` attributes they already know about.

    New attributes power the agentic pipeline:
      * ``id`` — UUID for this migration run.
      * ``pipeline_state`` — per-agent status & result references.
      * ``artifacts`` — intermediate outputs keyed by name.
      * ``messages`` — ordered list of inter-agent messages.
      * ``agent_traces`` — detailed execution records.
      * ``token_usage`` — cumulative tokens per agent.
      * ``total_cost_usd`` — estimated cost tracking.
    """

    def __init__(
        self,
        enabled: bool = False,
        llm_config: Optional[dict] = None,
        *,
        run_id: Optional[str] = None,
    ) -> None:
        super().__init__(enabled=enabled, llm_config=llm_config)

        # Identity
        self.id: str = run_id or uuid.uuid4().hex

        # Pipeline tracking
        self.pipeline_state: Dict[str, Dict[str, Any]] = {}
        self.artifacts: Dict[str, Any] = {
            "parsed_data": None,
            "generated_files": {},
            "review_feedback": [],
        }

        # Communication
        self.messages: List[AgentMessage] = []

        # Observability
        self.agent_traces: Dict[str, AgentTrace] = {}
        self.token_usage: Dict[str, int] = {}
        self.total_cost_usd: float = 0.0

        # Timestamps
        now = datetime.now(timezone.utc)
        self.created_at: datetime = now
        self.updated_at: datetime = now

        # Checkpoint storage (serialised snapshots keyed by agent name)
        self._checkpoints: Dict[str, dict] = {}

        logger.info("agent_context.created", run_id=self.id)

    # ------------------------------------------------------------------
    #  Core helpers
    # ------------------------------------------------------------------

    def update(self, agent_name: str, result: dict) -> None:
        """Record the result of an agent run in the pipeline state.

        Args:
            agent_name: Identifier of the agent that just ran.
            result: Arbitrary result dict produced by the agent.
        """
        self.pipeline_state[agent_name] = result
        self.updated_at = datetime.now(timezone.utc)
        logger.info("agent_context.updated", agent=agent_name, run_id=self.id)

    def get_agent_result(self, agent_name: str) -> Optional[dict]:
        """Retrieve a previously-stored agent result."""
        return self.pipeline_state.get(agent_name)

    # ------------------------------------------------------------------
    #  Artifact management
    # ------------------------------------------------------------------

    def set_artifact(self, key: str, value: Any) -> None:
        """Store an intermediate artifact."""
        self.artifacts[key] = value
        self.updated_at = datetime.now(timezone.utc)

    def get_artifact(self, key: str) -> Any:
        """Retrieve an artifact, returning ``None`` if absent."""
        return self.artifacts.get(key)

    # ------------------------------------------------------------------
    #  Inter-agent messaging
    # ------------------------------------------------------------------

    def send_message(
        self,
        sender: str,
        receiver: str,
        content: Any,
        msg_type: str = "info",
    ) -> None:
        """Post a message visible to the receiving agent."""
        msg = AgentMessage(
            sender=sender,
            receiver=receiver,
            content=content,
            msg_type=msg_type,
        )
        self.messages.append(msg)
        logger.debug(
            "agent_context.message",
            sender=sender,
            receiver=receiver,
            msg_type=msg_type,
        )

    def get_messages_for(self, agent_name: str) -> List[AgentMessage]:
        """Return messages addressed to *agent_name* or broadcast."""
        return [
            m for m in self.messages
            if m.receiver in (agent_name, "*")
        ]

    # ------------------------------------------------------------------
    #  Trace management
    # ------------------------------------------------------------------

    def start_trace(self, agent_name: str) -> AgentTrace:
        """Create and start a new trace for *agent_name*."""
        trace = AgentTrace(agent_name=agent_name)
        trace.mark_started()
        self.agent_traces[agent_name] = trace
        return trace

    def finish_trace(
        self,
        agent_name: str,
        status: str,
        token_usage: int = 0,
        error: Optional[str] = None,
        fallback_used: bool = False,
    ) -> None:
        """Finalise the trace for *agent_name*."""
        trace = self.agent_traces.get(agent_name)
        if trace is None:
            logger.warning("agent_context.no_trace", agent=agent_name)
            return
        trace.mark_finished(
            status=status,
            token_usage=token_usage,
            error=error,
            fallback_used=fallback_used,
        )
        # Accumulate token usage
        self.token_usage[agent_name] = (
            self.token_usage.get(agent_name, 0) + token_usage
        )
        self.updated_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    #  Checkpointing
    # ------------------------------------------------------------------

    def save_checkpoint(self, agent_name: str) -> None:
        """Snapshot current pipeline state so we can resume on failure."""
        self._checkpoints[agent_name] = {
            "pipeline_state": dict(self.pipeline_state),
            "artifacts": dict(self.artifacts),
            "token_usage": dict(self.token_usage),
            "total_cost_usd": self.total_cost_usd,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.debug("agent_context.checkpoint_saved", agent=agent_name)

    def restore_checkpoint(self, agent_name: str) -> bool:
        """Restore state from a checkpoint. Returns True on success."""
        cp = self._checkpoints.get(agent_name)
        if cp is None:
            return False
        self.pipeline_state = cp["pipeline_state"]
        self.artifacts = cp["artifacts"]
        self.token_usage = cp["token_usage"]
        self.total_cost_usd = cp["total_cost_usd"]
        logger.info("agent_context.checkpoint_restored", agent=agent_name)
        return True

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------

    def to_trace(self) -> dict:
        """Full execution trace suitable for storage / API response."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "pipeline_state": self.pipeline_state,
            "agent_traces": {
                name: trace.to_dict()
                for name, trace in self.agent_traces.items()
            },
            "token_usage": self.token_usage,
            "total_cost_usd": self.total_cost_usd,
            "messages": [m.to_dict() for m in self.messages],
            "legacy_summary": self.to_summary(),
        }

    def __repr__(self) -> str:
        agents_done = sum(
            1 for t in self.agent_traces.values() if t.status == "success"
        )
        return (
            f"<AgentContext id={self.id[:8]}... "
            f"agents={agents_done}/{len(self.agent_traces)} "
            f"tokens={sum(self.token_usage.values())}>"
        )
