"""
Azure OpenAI Provider — LLM integration for Azure-hosted OpenAI models.

Provides chat completions (GPT-4o) and embeddings (text-embedding-3-small)
through the Azure OpenAI Service, with retry logic, token counting, cost
tracking, and async support.

Requires:
  - ``openai>=1.0``
  - ``tiktoken``
  - ``httpx`` (for async operations)

Configuration is loaded from ``AzureOpenAISettings`` in ``api.config``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.migrator.llm_validator import BaseLLMProvider

logger = logging.getLogger(__name__)

# ── Cost table (USD per 1K tokens, as of 2024-12 Azure pricing) ──
_COST_PER_1K_TOKENS: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
}


@dataclass
class UsageMetrics:
    """Accumulated token usage and cost metrics."""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    request_count: int = 0
    errors: int = 0
    retries: int = 0
    history: List[Dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
    ) -> None:
        """Record a single API call's usage."""
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        total = prompt_tokens + completion_tokens
        self.total_tokens += total
        self.request_count += 1

        cost_table = _COST_PER_1K_TOKENS.get(model, {"input": 0.0, "output": 0.0})
        cost = (
            (prompt_tokens / 1000) * cost_table["input"]
            + (completion_tokens / 1000) * cost_table["output"]
        )
        self.total_cost_usd += cost

        self.history.append(
            {
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": round(cost, 6),
                "latency_ms": latency_ms,
            }
        )

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict suitable for logging or API response."""
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "request_count": self.request_count,
            "errors": self.errors,
            "retries": self.retries,
        }


def _count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Estimate token count using tiktoken (falls back to heuristic)."""
    try:
        import tiktoken

        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback heuristic: ~4 chars per token
        return len(text) // 4


class AzureOpenAIProvider(BaseLLMProvider):
    """
    Azure OpenAI provider for chat completions and embeddings.

    Wraps the ``openai.AzureOpenAI`` client with:
      - Configurable endpoint, API version, and deployment names
      - Exponential backoff retry (429 / 5xx)
      - Token counting via tiktoken
      - Cumulative cost tracking
      - Async support via ``httpx`` / ``openai.AsyncAzureOpenAI``
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
        *,
        endpoint: str = "",
        api_version: str = "2024-02-01",
        chat_deployment: str = "gpt-4o",
        embedding_deployment: str = "text-embedding-3-small",
        max_retries: int = 3,
        timeout_seconds: float = 120.0,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url)

        # Azure-specific config — fall back to env vars
        self.endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        self.api_version = api_version or os.environ.get(
            "AZURE_OPENAI_API_VERSION", "2024-02-01"
        )
        self.chat_deployment = chat_deployment or os.environ.get(
            "AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o"
        )
        self.embedding_deployment = embedding_deployment or os.environ.get(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
        )
        self._api_key = api_key or os.environ.get("AZURE_OPENAI_KEY", "")

        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

        # Lazy-initialized clients
        self._sync_client = None
        self._async_client = None

        # Metrics
        self.metrics = UsageMetrics()

    # ------------------------------------------------------------------
    #  Client initialization
    # ------------------------------------------------------------------

    def _get_sync_client(self):
        """Lazily create the synchronous Azure OpenAI client."""
        if self._sync_client is None:
            try:
                from openai import AzureOpenAI
            except ImportError:
                raise ImportError(
                    "The 'openai' package is required for Azure OpenAI. "
                    "Install it with: pip install openai>=1.0"
                )

            if not self.endpoint:
                raise ValueError(
                    "Azure OpenAI endpoint is required. Set AZURE_OPENAI_ENDPOINT "
                    "or pass endpoint= to the constructor."
                )
            if not self._api_key:
                raise ValueError(
                    "Azure OpenAI API key is required. Set AZURE_OPENAI_KEY "
                    "or pass api_key= to the constructor."
                )

            self._sync_client = AzureOpenAI(
                api_key=self._api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint,
                timeout=self.timeout_seconds,
                max_retries=0,  # We handle retries ourselves
            )
        return self._sync_client

    def _get_async_client(self):
        """Lazily create the asynchronous Azure OpenAI client."""
        if self._async_client is None:
            try:
                from openai import AsyncAzureOpenAI
            except ImportError:
                raise ImportError(
                    "The 'openai' package is required for Azure OpenAI. "
                    "Install it with: pip install openai>=1.0"
                )

            self._async_client = AsyncAzureOpenAI(
                api_key=self._api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint,
                timeout=self.timeout_seconds,
                max_retries=0,
            )
        return self._async_client

    # ------------------------------------------------------------------
    #  Retry logic
    # ------------------------------------------------------------------

    def _should_retry(self, exc: Exception) -> bool:
        """Determine if an exception is retryable."""
        try:
            from openai import (
                APIConnectionError,
                APITimeoutError,
                InternalServerError,
                RateLimitError,
            )

            return isinstance(
                exc,
                (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError),
            )
        except ImportError:
            return False

    def _get_retry_after(self, exc: Exception) -> Optional[float]:
        """Extract Retry-After header value from a rate limit error."""
        try:
            if hasattr(exc, "response") and exc.response is not None:
                retry_after = exc.response.headers.get("Retry-After")
                if retry_after:
                    return float(retry_after)
        except (ValueError, AttributeError):
            pass
        return None

    def _execute_with_retry(self, fn, *args, **kwargs):
        """Execute a callable with exponential backoff retry."""
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                if not self._should_retry(exc) or attempt == self.max_retries:
                    self.metrics.errors += 1
                    raise

                self.metrics.retries += 1
                retry_after = self._get_retry_after(exc)
                backoff = retry_after if retry_after else min(2**attempt, 60)

                logger.warning(
                    "Azure OpenAI request failed (attempt %d/%d), "
                    "retrying in %.1fs: %s",
                    attempt,
                    self.max_retries,
                    backoff,
                    str(exc),
                )
                time.sleep(backoff)

        # Should not reach here, but just in case
        raise last_error  # type: ignore[misc]

    async def _execute_with_retry_async(self, coro_fn, *args, **kwargs):
        """Execute an async callable with exponential backoff retry."""
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return await coro_fn(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                if not self._should_retry(exc) or attempt == self.max_retries:
                    self.metrics.errors += 1
                    raise

                self.metrics.retries += 1
                retry_after = self._get_retry_after(exc)
                backoff = retry_after if retry_after else min(2**attempt, 60)

                logger.warning(
                    "Azure OpenAI async request failed (attempt %d/%d), "
                    "retrying in %.1fs: %s",
                    attempt,
                    self.max_retries,
                    backoff,
                    str(exc),
                )
                await asyncio.sleep(backoff)

        raise last_error  # type: ignore[misc]

    # ------------------------------------------------------------------
    #  Chat completions (sync)
    # ------------------------------------------------------------------

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
    ) -> str:
        """
        Send a chat completion request to Azure OpenAI (synchronous).

        Parameters
        ----------
        system_prompt : str
            System-level instructions.
        user_prompt : str
            User message.
        max_tokens : int
            Maximum tokens in the response.

        Returns
        -------
        str
            The assistant's response text.

        Raises
        ------
        Exception
            On API errors after all retries are exhausted.
        """
        client = self._get_sync_client()
        deployment = self.model or self.chat_deployment

        # Token counting for budget awareness
        prompt_token_est = _count_tokens(system_prompt + user_prompt, deployment)
        logger.debug(
            "Azure OpenAI chat request: deployment=%s, est_prompt_tokens=%d",
            deployment,
            prompt_token_est,
        )

        start_ms = int(time.monotonic() * 1000)

        def _call():
            return client.chat.completions.create(
                model=deployment,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

        response = self._execute_with_retry(_call)
        latency_ms = int(time.monotonic() * 1000) - start_ms

        # Record usage
        usage = response.usage
        if usage:
            self.metrics.record(
                model=deployment,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                latency_ms=latency_ms,
            )

        content = response.choices[0].message.content or ""
        logger.debug(
            "Azure OpenAI chat response: tokens=%d, latency=%dms",
            usage.total_tokens if usage else 0,
            latency_ms,
        )
        return content

    # ------------------------------------------------------------------
    #  Chat completions (async)
    # ------------------------------------------------------------------

    async def achat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2048,
    ) -> str:
        """
        Send a chat completion request to Azure OpenAI (asynchronous).

        Parameters
        ----------
        system_prompt : str
            System-level instructions.
        user_prompt : str
            User message.
        max_tokens : int
            Maximum tokens in the response.

        Returns
        -------
        str
            The assistant's response text.
        """
        client = self._get_async_client()
        deployment = self.model or self.chat_deployment

        start_ms = int(time.monotonic() * 1000)

        async def _call():
            return await client.chat.completions.create(
                model=deployment,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

        response = await self._execute_with_retry_async(_call)
        latency_ms = int(time.monotonic() * 1000) - start_ms

        usage = response.usage
        if usage:
            self.metrics.record(
                model=deployment,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                latency_ms=latency_ms,
            )

        return response.choices[0].message.content or ""

    # ------------------------------------------------------------------
    #  Embeddings (sync)
    # ------------------------------------------------------------------

    def embed(self, text: str) -> List[float]:
        """
        Generate an embedding vector for a single text string.

        Uses the configured embedding deployment (default: text-embedding-3-small).

        Parameters
        ----------
        text : str
            Input text to embed.

        Returns
        -------
        List[float]
            Embedding vector.
        """
        client = self._get_sync_client()
        deployment = self.embedding_deployment

        start_ms = int(time.monotonic() * 1000)

        def _call():
            return client.embeddings.create(
                model=deployment,
                input=text,
            )

        response = self._execute_with_retry(_call)
        latency_ms = int(time.monotonic() * 1000) - start_ms

        usage = response.usage
        if usage:
            self.metrics.record(
                model=deployment,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=0,
                latency_ms=latency_ms,
            )

        return response.data[0].embedding

    def embed_batch(self, texts: List[str], batch_size: int = 16) -> List[List[float]]:
        """
        Generate embedding vectors for a batch of texts.

        The Azure OpenAI API supports batched input natively. Large batches
        are split into sub-batches of ``batch_size`` to stay within limits.

        Parameters
        ----------
        texts : List[str]
            Input texts.
        batch_size : int
            Maximum number of texts per API call.

        Returns
        -------
        List[List[float]]
            List of embedding vectors.
        """
        if not texts:
            return []

        client = self._get_sync_client()
        deployment = self.embedding_deployment
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            start_ms = int(time.monotonic() * 1000)

            def _call(batch_input=batch):
                return client.embeddings.create(
                    model=deployment,
                    input=batch_input,
                )

            response = self._execute_with_retry(_call)
            latency_ms = int(time.monotonic() * 1000) - start_ms

            usage = response.usage
            if usage:
                self.metrics.record(
                    model=deployment,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=0,
                    latency_ms=latency_ms,
                )

            # Sort by index to ensure correct order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            all_embeddings.extend([d.embedding for d in sorted_data])

        return all_embeddings

    # ------------------------------------------------------------------
    #  Embeddings (async)
    # ------------------------------------------------------------------

    async def aembed(self, text: str) -> List[float]:
        """Generate an embedding vector asynchronously."""
        client = self._get_async_client()
        deployment = self.embedding_deployment

        start_ms = int(time.monotonic() * 1000)

        async def _call():
            return await client.embeddings.create(
                model=deployment,
                input=text,
            )

        response = await self._execute_with_retry_async(_call)
        latency_ms = int(time.monotonic() * 1000) - start_ms

        usage = response.usage
        if usage:
            self.metrics.record(
                model=deployment,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=0,
                latency_ms=latency_ms,
            )

        return response.data[0].embedding

    async def aembed_batch(
        self, texts: List[str], batch_size: int = 16
    ) -> List[List[float]]:
        """Generate embedding vectors for a batch of texts asynchronously."""
        if not texts:
            return []

        client = self._get_async_client()
        deployment = self.embedding_deployment
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            start_ms = int(time.monotonic() * 1000)

            async def _call(batch_input=batch):
                return await client.embeddings.create(
                    model=deployment,
                    input=batch_input,
                )

            response = await self._execute_with_retry_async(_call)
            latency_ms = int(time.monotonic() * 1000) - start_ms

            usage = response.usage
            if usage:
                self.metrics.record(
                    model=deployment,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=0,
                    latency_ms=latency_ms,
                )

            sorted_data = sorted(response.data, key=lambda x: x.index)
            all_embeddings.extend([d.embedding for d in sorted_data])

        return all_embeddings

    # ------------------------------------------------------------------
    #  Validation (required by BaseLLMProvider)
    # ------------------------------------------------------------------

    def validate(self, files: dict, summary: dict) -> dict:
        """
        Validate generated code using Azure OpenAI.

        Implements the ``BaseLLMProvider.validate`` interface.
        """
        from backend.migrator.llm_validator import (
            VALIDATION_SYSTEM_PROMPT,
            _api_error,
            _build_validation_prompt,
        )

        user_prompt = _build_validation_prompt(files, summary)

        try:
            response_text = self.chat(
                system_prompt=VALIDATION_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=4096,
            )
            return self._parse_response(response_text)
        except Exception as e:
            return _api_error("Azure OpenAI", str(e))

    # ------------------------------------------------------------------
    #  Utility
    # ------------------------------------------------------------------

    def count_tokens(self, text: str) -> int:
        """Count tokens for the configured chat model."""
        return _count_tokens(text, self.model or self.chat_deployment)

    def get_metrics(self) -> Dict[str, Any]:
        """Return accumulated usage metrics."""
        return self.metrics.summary()

    def reset_metrics(self) -> None:
        """Reset all accumulated metrics."""
        self.metrics = UsageMetrics()

    def close(self) -> None:
        """Close underlying HTTP clients."""
        if self._sync_client is not None:
            try:
                self._sync_client.close()
            except Exception:
                pass
            self._sync_client = None
        if self._async_client is not None:
            try:
                # Async client close needs to be awaited, but we're in sync context
                # Just drop the reference; httpx will clean up on GC
                pass
            except Exception:
                pass
            self._async_client = None

    async def aclose(self) -> None:
        """Close underlying HTTP clients (async)."""
        self.close()
        if self._async_client is not None:
            try:
                await self._async_client.close()
            except Exception:
                pass
            self._async_client = None

    def __repr__(self) -> str:
        return (
            f"AzureOpenAIProvider("
            f"endpoint={self.endpoint!r}, "
            f"chat_deployment={self.chat_deployment!r}, "
            f"embedding_deployment={self.embedding_deployment!r}, "
            f"api_version={self.api_version!r})"
        )
