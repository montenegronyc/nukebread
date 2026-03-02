"""Ollama embedding client for NukeBread RAG.

Uses nomic-embed-text (768 dimensions) running locally via Ollama.
"""

from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error

logger = logging.getLogger("nukebread.rag.embeddings")

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768


class OllamaEmbedder:
    """Thin client for the Ollama embedding API."""

    def __init__(
        self,
        base_url: str = OLLAMA_URL,
        model: str = EMBED_MODEL,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def embed(self, text: str) -> list[float]:
        """Embed a single text string. Returns a 768-dim vector."""
        body = json.dumps({"model": self.model, "input": text}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/embed",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        embeddings = data.get("embeddings", [])
        if not embeddings:
            raise RuntimeError("Ollama returned no embeddings")
        vec = embeddings[0]
        if len(vec) != EMBED_DIM:
            logger.warning(
                "Expected %d dimensions, got %d", EMBED_DIM, len(vec)
            )
        return vec

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in one call. Ollama supports batch input."""
        if not texts:
            return []
        body = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/embed",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("embeddings", [])

    def is_available(self) -> bool:
        """Check if Ollama is reachable and the embedding model is loaded."""
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in data.get("models", [])]
            return any(self.model in m for m in models)
        except Exception:
            return False
