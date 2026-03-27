"""
Embedding service for the RAG subsystem.

Provides a thread-safe singleton that lazily loads a sentence-transformer model,
auto-detects the best available device (CUDA > MPS > CPU), and exposes methods
for single and batch embedding with L2 normalization.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from api.rag.config import RAGConfig, rag_config

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Metadata about the loaded embedding model."""

    name: str
    dim: int
    device: str
    max_seq_length: int


class EmbeddingService:
    """
    Thread-safe singleton embedding service backed by sentence-transformers.

    Usage::

        svc = EmbeddingService.get_instance()
        vec = svc.embed("Some text")
        vecs = svc.embed_batch(["text1", "text2"])
    """

    _instance: Optional["EmbeddingService"] = None
    _lock = threading.Lock()

    def __init__(self, config: RAGConfig | None = None) -> None:
        self._config = config or rag_config
        self._model = None
        self._model_lock = threading.Lock()
        self._device: str = "cpu"
        self._model_info: Optional[ModelInfo] = None

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls, config: RAGConfig | None = None) -> "EmbeddingService":
        """Return the global singleton, creating it on first call."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Discard the singleton (useful in tests)."""
        with cls._lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Device detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_device() -> str:
        """Pick the best available compute device."""
        try:
            import torch

            if torch.cuda.is_available():
                logger.info("CUDA device detected; using GPU.")
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                logger.info("Apple MPS device detected; using Metal GPU.")
                return "mps"
        except ImportError:
            logger.warning("PyTorch not installed; falling back to CPU.")
        logger.info("Using CPU for embeddings.")
        return "cpu"

    # ------------------------------------------------------------------
    # Lazy model loading
    # ------------------------------------------------------------------

    def _ensure_model(self) -> None:
        """Load the model if it has not been loaded yet (double-checked locking)."""
        if self._model is not None:
            return
        with self._model_lock:
            if self._model is not None:
                return
            self._device = self._detect_device()
            model_name = self._config.embedding.model_name
            logger.info("Loading embedding model '%s' on device '%s' ...", model_name, self._device)
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(model_name, device=self._device)
                self._model_info = ModelInfo(
                    name=model_name,
                    dim=self._model.get_sentence_embedding_dimension(),
                    device=self._device,
                    max_seq_length=self._model.max_seq_length,
                )
                logger.info(
                    "Embedding model loaded: dim=%d, max_seq_length=%d",
                    self._model_info.dim,
                    self._model_info.max_seq_length,
                )
            except Exception:
                logger.exception("Failed to load embedding model '%s'.", model_name)
                raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def model_info(self) -> ModelInfo:
        """Return metadata about the loaded model (loads the model if needed)."""
        self._ensure_model()
        assert self._model_info is not None
        return self._model_info

    def embed(self, text: str) -> List[float]:
        """
        Generate an L2-normalized embedding for a single text string.

        Args:
            text: The input text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        self._ensure_model()
        assert self._model is not None
        embedding: np.ndarray = self._model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=self._config.embedding.normalize,
            show_progress_bar=False,
        )
        return self._normalize_l2(embedding).tolist()

    def embed_batch(
        self, texts: List[str], batch_size: int | None = None
    ) -> List[List[float]]:
        """
        Generate L2-normalized embeddings for a batch of texts.

        Args:
            texts: List of input texts.
            batch_size: Override the default batch size from config.

        Returns:
            A list of embedding vectors (each a list of floats).
        """
        if not texts:
            return []
        self._ensure_model()
        assert self._model is not None
        bs = batch_size or self._config.embedding.batch_size
        embeddings: np.ndarray = self._model.encode(
            texts,
            batch_size=bs,
            convert_to_numpy=True,
            normalize_embeddings=self._config.embedding.normalize,
            show_progress_bar=False,
        )
        normalized = self._normalize_l2_batch(embeddings)
        return normalized.tolist()

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_l2(vec: np.ndarray) -> np.ndarray:
        """L2-normalize a single vector."""
        norm = np.linalg.norm(vec)
        if norm == 0:
            return vec
        return vec / norm

    @staticmethod
    def _normalize_l2_batch(matrix: np.ndarray) -> np.ndarray:
        """L2-normalize each row of a 2-D matrix."""
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        return matrix / norms
