"""Thin wrapper around Sentence-Transformers.

Keeping the import isolated here means the rest of the app never has to
know which embedding library is in use, and the (slow) torch/transformers
import only happens if RAG is actually enabled and a query is made -
`RAG_ENABLED=false` deployments never pay for it.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.config import settings
from app.utils import get_logger

logger = get_logger(__name__)


@lru_cache
def _load_model():
    """Lazily import and cache the SentenceTransformer model as a singleton."""
    from sentence_transformers import SentenceTransformer

    logger.info("loading_embedding_model", extra={"model": settings.embedding_model_name})
    return SentenceTransformer(settings.embedding_model_name)


def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a batch of texts, returning an (N, D) float32 array, L2-normalized."""
    if not texts:
        return np.zeros((0, embedding_dim()), dtype="float32")
    vectors = _load_model().encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,  # so FAISS inner product == cosine similarity
        show_progress_bar=False,
    )
    return vectors.astype("float32")


def embed_query(text: str) -> np.ndarray:
    """Embed a single query string, returning a (D,) float32 vector."""
    return embed_texts([text])[0]


@lru_cache
def embedding_dim() -> int:
    """Embedding dimensionality for the configured model (384 for MiniLM-L6-v2)."""
    return _load_model().get_sentence_embedding_dimension()
