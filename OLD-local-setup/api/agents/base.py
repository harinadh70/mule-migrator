"""
BaseAgent — abstract base class for every agent in the migration pipeline.

Provides:
  - LLM calling with exponential-backoff retry
  - Token budget enforcement
  - RAG context injection
  - Structured response parsing
  - Deterministic fallback when LLM is unavailable
  - Structured metric emission via structlog
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import structlog

from api.agents.context import AgentContext
from api.agents.result import AgentResult
from backend.migrator.llm_validator import BaseLLMProvider, get_provider

if TYPE_CHECKING:
    # Avoid hard import-time dependency on the RAG layer which may not be
    # fully installed yet.
    from api.rag.retriever import HybridRetriever

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """Abstract base for all pipeline agents.

    Sub-classes must implement:
      - ``execute(context)`` — the main agent logic
      - ``get_fallback(context)`` — deterministic fallback output

    They *may* override:
      - ``build_prompt(context, rag_context)``
      - ``parse_response(response)``
    """

    # ------------------------------------------------------------------
    #  Class-level defaults (overridden by sub-classes)
    # ------------------------------------------------------------------
    name: str = "base"
    role: str = "generic agent"
    system_prompt: str = "You are a helpful assistant."

    def __init__(
        self,
        llm_provider: Optional[BaseLLMProvider] = None,
        llm_config: Optional[dict] = None,
        retriever: Optional["HybridRetriever"] = None,
        *,
        max_retries: int = 3,
        timeout_seconds: int = 120,
        token_budget: int = 8000,
    ) -> None:
        # LLM provider — either directly supplied or lazily built from config
        self._llm_provider = llm_provider
        self._llm_config = llm_config or {}
        self.retriever = retriever

        # Operational knobs
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.token_budget = token_budget

    # ------------------------------------------------------------------
    #  LLM provider (lazy)
    # ------------------------------------------------------------------

    @property
    def llm_provider(self) -> Optional[BaseLLMProvider]:
        if self._llm_provider is not None:
            return self._llm_provider
        if self._llm_config.get("provider"):
            # Get API key from config, or fall back to environment settings
            api_key = self._llm_config.get("apiKey", "")
            if not api_key:
                try:
                    from api.config import get_settings
                    settings = get_settings()
                    provider = self._llm_config["provider"]
                    key_map = {
                        "anthropic": settings.llm.anthropic_api_key,
                        "openai": settings.llm.openai_api_key,
                        "google": settings.llm.google_api_key,
                        "groq": settings.llm.groq_api_key,
                        "deepseek": settings.llm.deepseek_api_key,
                    }
                    api_key = key_map.get(provider, "") or ""
                except Exception:
                    pass
            self._llm_provider = get_provider(
                self._llm_config["provider"],
                api_key=api_key,
                model=self._llm_config.get("model", ""),
                base_url=self._llm_config.get("baseUrl", ""),
            )
            return self._llm_provider
        return None

    # ------------------------------------------------------------------
    #  Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """Run the agent's core logic. Must be implemented by sub-classes."""
        ...

    @abstractmethod
    def get_fallback(self, context: AgentContext) -> dict:
        """Return a deterministic fallback when the LLM is unavailable."""
        ...

    # ------------------------------------------------------------------
    #  Prompt construction
    # ------------------------------------------------------------------

    def build_prompt(self, context: AgentContext, rag_context: str = "") -> str:
        """Build the user prompt combining context and RAG results.

        Sub-classes typically override this to inject domain-specific info.
        """
        parts: List[str] = []
        if rag_context:
            parts.append("=== Relevant knowledge (from RAG) ===")
            parts.append(rag_context)
            parts.append("=== End knowledge ===\n")
        parts.append("Please proceed with the task based on the above context.")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    #  RAG helpers
    # ------------------------------------------------------------------

    async def query_rag(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Query the retriever and return a list of result dicts.

        Returns an empty list if no retriever is configured.
        """
        if self.retriever is None:
            return []
        try:
            # HybridRetriever.search is expected to be sync; run in executor
            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(
                None, self.retriever.search, query, top_k,
            )
            return results if isinstance(results, list) else []
        except Exception as exc:
            logger.warning("rag_query.failed", agent=self.name, error=str(exc))
            return []

    def format_rag_results(self, results: List[Dict[str, Any]]) -> str:
        """Format RAG results into a context string for the prompt."""
        if not results:
            return ""
        parts: List[str] = []
        for i, r in enumerate(results, 1):
            text = r.get("text", r.get("content", ""))
            source = r.get("source", r.get("metadata", {}).get("source", "unknown"))
            score = r.get("score", 0.0)
            parts.append(f"[{i}] (score={score:.2f}, source={source})\n{text}\n")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    #  LLM calling with retry
    # ------------------------------------------------------------------

    async def call_llm_with_retry(self, prompt: str) -> str:
        """Call the LLM with exponential-backoff retry.

        Raises:
            RuntimeError: If all retries are exhausted or no provider is set.
        """
        provider = self.llm_provider
        if provider is None:
            raise RuntimeError(f"[{self.name}] No LLM provider configured")

        self.validate_token_budget(prompt)

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                loop = asyncio.get_running_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        provider.chat,
                        self.system_prompt,
                        prompt,
                        min(self.token_budget, 4096),
                    ),
                    timeout=self.timeout_seconds,
                )
                return response
            except asyncio.TimeoutError:
                last_error = TimeoutError(
                    f"LLM call timed out after {self.timeout_seconds}s "
                    f"(attempt {attempt}/{self.max_retries})"
                )
                logger.warning(
                    "llm_call.timeout",
                    agent=self.name,
                    attempt=attempt,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "llm_call.error",
                    agent=self.name,
                    attempt=attempt,
                    error=str(exc),
                )

            if attempt < self.max_retries:
                backoff = min(2 ** attempt, 30)
                await asyncio.sleep(backoff)

        raise RuntimeError(
            f"[{self.name}] LLM call failed after {self.max_retries} retries: {last_error}"
        )

    # ------------------------------------------------------------------
    #  Response parsing
    # ------------------------------------------------------------------

    def parse_response(self, response: str) -> dict:
        """Extract structured JSON data from an LLM response.

        Handles markdown fences, bare JSON, and partial extraction.
        """
        text = response.strip()

        # Strip markdown fences
        if text.startswith("```"):
            text = re.sub(r"^```(?:json|java)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find the largest JSON object
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Return raw text wrapped in a dict
        return {"raw_response": text}

    def extract_code_block(self, response: str, language: str = "java") -> str:
        """Extract a fenced code block from the LLM response."""
        pattern = rf"```(?:{language})?\s*\n(.*?)```"
        m = re.search(pattern, response, re.DOTALL)
        if m:
            return m.group(1).strip()
        return response.strip()

    # ------------------------------------------------------------------
    #  Token budget
    # ------------------------------------------------------------------

    def validate_token_budget(self, prompt: str) -> None:
        """Rough check that the prompt fits the token budget.

        Uses the heuristic of ~4 characters per token.  Raises
        ``ValueError`` if the prompt is too large.
        """
        estimated_tokens = len(prompt) // 4
        if estimated_tokens > self.token_budget:
            raise ValueError(
                f"[{self.name}] Prompt exceeds token budget: "
                f"~{estimated_tokens} estimated vs {self.token_budget} budget"
            )

    # ------------------------------------------------------------------
    #  Metrics
    # ------------------------------------------------------------------

    def emit_metrics(self, duration_ms: int, tokens: int, status: str) -> None:
        """Emit structured log metrics for observability."""
        logger.info(
            "agent.metrics",
            agent=self.name,
            role=self.role,
            duration_ms=duration_ms,
            tokens=tokens,
            status=status,
        )

    # ------------------------------------------------------------------
    #  Safe execution wrapper
    # ------------------------------------------------------------------

    async def safe_execute(self, context: AgentContext) -> AgentResult:
        """Run ``execute()`` with full error handling, tracing, and metrics.

        This is what the orchestrator calls; sub-classes implement ``execute()``.
        """
        trace = context.start_trace(self.name)
        start = time.monotonic()

        try:
            result = await asyncio.wait_for(
                self.execute(context),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start) * 1000)
            context.finish_trace(self.name, status="timeout")
            self.emit_metrics(duration_ms, 0, "timeout")
            return AgentResult.timeout(duration_ms=duration_ms)
        except ValueError as exc:
            # Token budget exceeded
            duration_ms = int((time.monotonic() - start) * 1000)
            context.finish_trace(self.name, status="budget_exceeded", error=str(exc))
            self.emit_metrics(duration_ms, 0, "budget_exceeded")
            return AgentResult.budget_exceeded(duration_ms=duration_ms)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "agent.execute.failed",
                agent=self.name,
                error=str(exc),
                exc_info=True,
            )
            # Try deterministic fallback
            try:
                fallback_output = self.get_fallback(context)
                context.finish_trace(
                    self.name, status="error", error=str(exc), fallback_used=True,
                )
                self.emit_metrics(duration_ms, 0, "fallback")
                return AgentResult.from_error(
                    error=str(exc),
                    fallback_output=fallback_output,
                    duration_ms=duration_ms,
                )
            except Exception as fb_exc:
                context.finish_trace(self.name, status="error", error=str(exc))
                self.emit_metrics(duration_ms, 0, "error")
                return AgentResult.from_error(
                    error=f"{exc} (fallback also failed: {fb_exc})",
                    duration_ms=duration_ms,
                )

        # Happy path
        duration_ms = int((time.monotonic() - start) * 1000)
        context.finish_trace(
            self.name,
            status=result.status,
            token_usage=result.token_usage,
            fallback_used=result.fallback_used,
        )
        # Propagate RAG info to trace
        trace.rag_queries = result.rag_queries
        trace.rag_results_used = result.rag_results_used
        result.duration_ms = duration_ms
        self.emit_metrics(duration_ms, result.token_usage, result.status)
        return result
