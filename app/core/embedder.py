"""
Embedder module for generating text embeddings using OpenAI's API.
"""

import logging
import os
import time
from typing import List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


class Embedder:
    """Handles text embedding generation using OpenAI's embedding models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ):
        """
        Initialize the embedder.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Embedding model to use
            dimensions: Output dimensions for the embedding
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key must be provided or set in OPENAI_API_KEY env var"
            )

        self.timeout_seconds = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "90"))
        self.retry_attempts = max(1, int(os.getenv("EMBEDDING_RETRY_ATTEMPTS", "3")))
        self.client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        self.model = model
        self.dimensions = dimensions

        logger.info(
            f"Initialized embedder with model={model}, dimensions={dimensions}, "
            f"timeout={self.timeout_seconds}s, retries={self.retry_attempts}"
        )

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text string.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        if not text or not text.strip():
            logger.warning("Attempted to embed empty text, returning zero vector")
            return [0.0] * self.dimensions

        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = self.client.embeddings.create(
                    model=self.model, input=text.strip(), dimensions=self.dimensions
                )

                embedding = response.data[0].embedding
                logger.debug(f"Generated embedding for text (length={len(text)})")
                return embedding
            except Exception as e:
                if attempt >= self.retry_attempts:
                    logger.error(f"Failed to generate embedding: {e}")
                    raise
                backoff = min(2 ** (attempt - 1), 8)
                logger.warning(
                    f"Embedding request failed (attempt {attempt}/{self.retry_attempts}): "
                    f"{e}. Retrying in {backoff}s..."
                )
                time.sleep(backoff)

    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process per API call (max 2048 for OpenAI)

        Returns:
            List of embedding vectors in the same order as input texts
        """
        if not texts:
            return []

        all_embeddings = []

        # Process in batches to avoid API limits
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # Filter out empty strings
            valid_texts = [t.strip() if t else "" for t in batch]

            for attempt in range(1, self.retry_attempts + 1):
                try:
                    response = self.client.embeddings.create(
                        model=self.model, input=valid_texts, dimensions=self.dimensions
                    )

                    batch_embeddings = [item.embedding for item in response.data]
                    all_embeddings.extend(batch_embeddings)

                    logger.info(
                        f"Generated {len(batch_embeddings)} embeddings "
                        f"(batch {i // batch_size + 1})"
                    )
                    break

                except Exception as e:
                    if attempt >= self.retry_attempts:
                        logger.error(
                            f"Failed to generate embeddings for batch {i // batch_size + 1}: {e}"
                        )
                        raise
                    backoff = min(2 ** (attempt - 1), 8)
                    logger.warning(
                        f"Embedding batch {i // batch_size + 1} failed "
                        f"(attempt {attempt}/{self.retry_attempts}): {e}. "
                        f"Retrying in {backoff}s..."
                    )
                    time.sleep(backoff)

        return all_embeddings

    def embed_concept(
        self, concept_text: str, book_context: Optional[str] = None
    ) -> List[float]:
        """
        Generate embedding for a concept, optionally with book context.

        Args:
            concept_text: The concept text (e.g., "oral_tradition")
            book_context: Optional book title or context to improve embedding

        Returns:
            Embedding vector
        """
        # Convert snake_case to readable text
        readable = concept_text.replace("_", " ")

        if book_context:
            text = f"{readable} (from {book_context})"
        else:
            text = readable

        return self.embed(text)
