"""
AgentResult — standardised return value from every agent execution.

Every ``BaseAgent.execute()`` returns an ``AgentResult`` so that the
orchestrator can uniformly inspect status, token usage, timings,
RAG attribution, and errors without knowing agent internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class AgentResult:
    """Immutable-ish result produced by a single agent run.

    Attributes:
        status: Outcome of the agent run.
        output: Agent-specific payload (generated code, review scores, etc.).
        token_usage: Total tokens consumed (prompt + completion).
        duration_ms: Wall-clock execution time in milliseconds.
        rag_queries: Queries sent to the retriever during this run.
        rag_results_used: How many retrieved chunks actually influenced the output.
        error: Human-readable error message when ``status`` is not ``success``.
        fallback_used: Whether a deterministic fallback was used instead of LLM.
        metadata: Arbitrary extra data agents can attach.
    """

    status: Literal["success", "partial", "error", "timeout", "budget_exceeded"] = "success"
    output: Dict[str, Any] = field(default_factory=dict)
    token_usage: int = 0
    duration_ms: int = 0
    rag_queries: List[str] = field(default_factory=list)
    rag_results_used: int = 0
    error: Optional[str] = None
    fallback_used: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    #  Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def success(
        cls,
        output: Dict[str, Any],
        token_usage: int = 0,
        duration_ms: int = 0,
        rag_queries: Optional[List[str]] = None,
        rag_results_used: int = 0,
        **metadata: Any,
    ) -> AgentResult:
        """Shorthand for a successful result."""
        return cls(
            status="success",
            output=output,
            token_usage=token_usage,
            duration_ms=duration_ms,
            rag_queries=rag_queries or [],
            rag_results_used=rag_results_used,
            metadata=metadata,
        )

    @classmethod
    def partial(
        cls,
        output: Dict[str, Any],
        error: str,
        token_usage: int = 0,
        duration_ms: int = 0,
        **metadata: Any,
    ) -> AgentResult:
        """Shorthand for a partially-successful result."""
        return cls(
            status="partial",
            output=output,
            error=error,
            token_usage=token_usage,
            duration_ms=duration_ms,
            metadata=metadata,
        )

    @classmethod
    def from_error(
        cls,
        error: str,
        fallback_output: Optional[Dict[str, Any]] = None,
        duration_ms: int = 0,
    ) -> AgentResult:
        """Shorthand for an error result, optionally with fallback output."""
        return cls(
            status="error",
            output=fallback_output or {},
            error=error,
            duration_ms=duration_ms,
            fallback_used=fallback_output is not None,
        )

    @classmethod
    def timeout(cls, duration_ms: int = 0) -> AgentResult:
        return cls(
            status="timeout",
            error="Agent execution timed out",
            duration_ms=duration_ms,
        )

    @classmethod
    def budget_exceeded(cls, token_usage: int = 0, duration_ms: int = 0) -> AgentResult:
        return cls(
            status="budget_exceeded",
            error="Token budget exceeded",
            token_usage=token_usage,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------
    #  Predicates
    # ------------------------------------------------------------------

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    @property
    def is_usable(self) -> bool:
        """True if output is usable (success or partial)."""
        return self.status in ("success", "partial")

    # ------------------------------------------------------------------
    #  Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "output": self.output,
            "token_usage": self.token_usage,
            "duration_ms": self.duration_ms,
            "rag_queries": self.rag_queries,
            "rag_results_used": self.rag_results_used,
            "error": self.error,
            "fallback_used": self.fallback_used,
            "metadata": self.metadata,
        }
