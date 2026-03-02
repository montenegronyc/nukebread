"""CompPatternStore — CRUD + vector search for the comp pattern library.

Manages PostgreSQL connection pool and provides methods for storing,
retrieving, and searching comp patterns with semantic embeddings.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Generator

import psycopg2
import psycopg2.pool
import psycopg2.extras

from nukebread.server.rag.embeddings import OllamaEmbedder
from nukebread.server.rag.formats import (
    graph_to_text,
    classify_pattern,
    extract_node_classes,
)
from nukebread.server.rag.nk_parser import build_connections_summary

logger = logging.getLogger("nukebread.rag.store")

DB_URL = os.environ.get(
    "NUKEBREAD_DB_URL",
    "postgresql://nukebread:nukebread@localhost:5434/nukebread",
)


@dataclass
class SearchResult:
    """A single search result from the pattern library."""

    pattern_id: int
    name: str
    description: str
    category: str
    similarity: float
    node_count: int = 0
    avg_score: float | None = None
    graph_json: dict | None = None


class CompPatternStore:
    """Vector-backed comp pattern library with semantic search."""

    def __init__(self, db_url: str | None = None) -> None:
        self._db_url = db_url or DB_URL
        self._pool: psycopg2.pool.ThreadedConnectionPool | None = None
        self._embedder = OllamaEmbedder()

    def _get_pool(self) -> psycopg2.pool.ThreadedConnectionPool:
        """Lazy-init connection pool."""
        if self._pool is None:
            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=5, dsn=self._db_url,
            )
        return self._pool

    @contextmanager
    def _conn(self) -> Generator:
        """Get a connection from the pool with auto-commit/rollback."""
        pool = self._get_pool()
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.putconn(conn)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def save_pattern(
        self,
        name: str,
        description: str,
        graph_dict: dict,
        category: str | None = None,
        use_cases: list[str] | None = None,
        prerequisites: list[str] | None = None,
        source_script: str | None = None,
        source_type: str = "manual",
        tags: list[str] | None = None,
    ) -> int:
        """Store a new comp pattern. Returns the pattern_id."""
        if category is None:
            category = classify_pattern(graph_dict)

        node_classes = extract_node_classes(graph_dict)
        node_count = len(graph_dict.get("nodes", []))
        conn_summary = build_connections_summary(graph_dict.get("nodes", []))

        with self._conn() as conn:
            cur = conn.cursor()

            # Insert pattern metadata
            cur.execute(
                """
                INSERT INTO comp_patterns
                    (name, description, category, use_cases, prerequisites,
                     node_classes, node_count, connections_summary,
                     source_script, source_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    name, description, category,
                    use_cases or [], prerequisites or [],
                    node_classes, node_count, conn_summary,
                    source_script, source_type,
                ),
            )
            pattern_id: int = cur.fetchone()[0]

            # Store graph JSON
            cur.execute(
                "INSERT INTO pattern_graphs (pattern_id, graph_json) VALUES (%s, %s)",
                (pattern_id, json.dumps(graph_dict)),
            )

            # Store tags
            if tags:
                for tag in tags:
                    cur.execute(
                        """
                        INSERT INTO pattern_tags (pattern_id, tag)
                        VALUES (%s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (pattern_id, tag),
                    )

            # Generate and store embeddings
            embed_text = f"{name}\n{description}\n{graph_to_text(graph_dict)}"
            chunks = self._chunk_text(embed_text)

            try:
                embeddings = self._embedder.embed_batch(chunks)
                for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                    cur.execute(
                        """
                        INSERT INTO pattern_chunks
                            (pattern_id, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s::vector)
                        """,
                        (pattern_id, i, chunk, str(emb)),
                    )
            except Exception:
                # Store chunks without embeddings — can regenerate later
                logger.warning(
                    "Ollama unavailable, storing pattern %d without embeddings",
                    pattern_id,
                )
                for i, chunk in enumerate(chunks):
                    cur.execute(
                        """
                        INSERT INTO pattern_chunks
                            (pattern_id, chunk_index, content)
                        VALUES (%s, %s, %s)
                        """,
                        (pattern_id, i, chunk),
                    )

        logger.info("Saved pattern %d: %s (%s)", pattern_id, name, category)
        return pattern_id

    def rate_pattern(
        self,
        pattern_id: int,
        success: bool,
        score: int | None = None,
        notes: str | None = None,
    ) -> None:
        """Record a success/failure rating for a pattern."""
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO pattern_ratings (pattern_id, success, score, notes)
                VALUES (%s, %s, %s, %s)
                """,
                (pattern_id, success, score, notes),
            )

    def delete_pattern(self, pattern_id: int) -> bool:
        """Delete a pattern and all associated data (cascading)."""
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM comp_patterns WHERE id = %s", (pattern_id,)
            )
            return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
        node_classes: list[str] | None = None,
        include_graph: bool = False,
    ) -> list[SearchResult]:
        """Semantic search for comp patterns.

        Returns top_k most similar patterns, optionally filtered by
        category or required node classes.
        """
        query_embedding = self._embed_query(query)

        with self._conn() as conn:
            cur = conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            )

            where_clauses: list[str] = []
            params: list[Any] = [str(query_embedding)]

            if category:
                where_clauses.append("cp.category = %s")
                params.append(category)

            if node_classes:
                where_clauses.append("cp.node_classes @> %s")
                params.append(node_classes)

            where_sql = ""
            if where_clauses:
                where_sql = "AND " + " AND ".join(where_clauses)

            params.append(top_k)

            sql = f"""
                SELECT sub.* FROM (
                    SELECT DISTINCT ON (cp.id)
                        cp.id AS pattern_id,
                        cp.name,
                        cp.description,
                        cp.category,
                        cp.node_count,
                        1 - (pc.embedding <=> %s::vector) AS similarity,
                        (SELECT AVG(pr.score)
                         FROM pattern_ratings pr
                         WHERE pr.pattern_id = cp.id) AS avg_score
                    FROM pattern_chunks pc
                    JOIN comp_patterns cp ON pc.pattern_id = cp.id
                    WHERE pc.embedding IS NOT NULL
                    {where_sql}
                    ORDER BY cp.id, (pc.embedding <=> %s::vector) ASC
                ) sub
                ORDER BY sub.similarity DESC
                LIMIT %s
            """

            # Need query embedding twice (once for similarity, once for ordering)
            params_full = [params[0]] + params[1:-1] + [params[0], params[-1]]
            cur.execute(sql, params_full)
            rows = cur.fetchall()

            results: list[SearchResult] = []
            for row in rows:
                result = SearchResult(
                    pattern_id=row["pattern_id"],
                    name=row["name"],
                    description=row["description"],
                    category=row["category"],
                    node_count=row["node_count"],
                    similarity=float(row["similarity"]),
                    avg_score=(
                        float(row["avg_score"])
                        if row["avg_score"] is not None
                        else None
                    ),
                )

                if include_graph:
                    cur.execute(
                        "SELECT graph_json FROM pattern_graphs WHERE pattern_id = %s",
                        (row["pattern_id"],),
                    )
                    graph_row = cur.fetchone()
                    if graph_row:
                        result.graph_json = graph_row["graph_json"]

                results.append(result)

        return results

    def get_pattern(
        self, pattern_id: int, include_graph: bool = True
    ) -> dict | None:
        """Get a single pattern by ID."""
        with self._conn() as conn:
            cur = conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            cur.execute(
                "SELECT * FROM comp_patterns WHERE id = %s", (pattern_id,)
            )
            row = cur.fetchone()
            if not row:
                return None

            result = dict(row)

            if include_graph:
                cur.execute(
                    "SELECT graph_json FROM pattern_graphs WHERE pattern_id = %s",
                    (pattern_id,),
                )
                g = cur.fetchone()
                result["graph_json"] = g["graph_json"] if g else None

            # Include tags
            cur.execute(
                "SELECT tag FROM pattern_tags WHERE pattern_id = %s",
                (pattern_id,),
            )
            result["tags"] = [r["tag"] for r in cur.fetchall()]

            # Include ratings summary
            cur.execute(
                """
                SELECT COUNT(*) as count,
                       AVG(score) as avg_score,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes
                FROM pattern_ratings WHERE pattern_id = %s
                """,
                (pattern_id,),
            )
            ratings = cur.fetchone()
            result["ratings"] = dict(ratings) if ratings else {}

            return result

    def list_patterns(
        self,
        category: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List patterns with optional category filter."""
        with self._conn() as conn:
            cur = conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            if category:
                cur.execute(
                    """
                    SELECT id, name, description, category, node_count,
                           source_type, created_at
                    FROM comp_patterns
                    WHERE category = %s
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (category, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT id, name, description, category, node_count,
                           source_type, created_at
                    FROM comp_patterns
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            return [dict(r) for r in cur.fetchall()]

    def stats(self) -> dict:
        """Return database statistics."""
        with self._conn() as conn:
            cur = conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            cur.execute("SELECT COUNT(*) AS total FROM comp_patterns")
            total = cur.fetchone()["total"]

            cur.execute(
                """
                SELECT category, COUNT(*) AS count
                FROM comp_patterns
                GROUP BY category
                ORDER BY count DESC
                """
            )
            by_category = {r["category"]: r["count"] for r in cur.fetchall()}

            cur.execute(
                "SELECT COUNT(*) AS total FROM pattern_chunks WHERE embedding IS NOT NULL"
            )
            embedded = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM pattern_ratings")
            ratings = cur.fetchone()["total"]

            return {
                "total_patterns": total,
                "by_category": by_category,
                "embedded_chunks": embedded,
                "total_ratings": ratings,
            }

    def regenerate_embeddings(self, limit: int = 1000) -> int:
        """Regenerate embeddings for chunks that are missing them."""
        with self._conn() as conn:
            cur = conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            cur.execute(
                """
                SELECT id, content FROM pattern_chunks
                WHERE embedding IS NULL
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

            if not rows:
                return 0

            texts = [r["content"] for r in rows]
            ids = [r["id"] for r in rows]

            # Batch embed
            embeddings = self._embedder.embed_batch(texts)

            for chunk_id, emb in zip(ids, embeddings):
                cur.execute(
                    "UPDATE pattern_chunks SET embedding = %s::vector WHERE id = %s",
                    (str(emb), chunk_id),
                )

        logger.info("Regenerated %d embeddings", len(rows))
        return len(rows)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _chunk_text(
        self,
        text: str,
        target_tokens: int = 750,
    ) -> list[str]:
        """Split text into chunks for embedding.

        Comp patterns are typically short enough for a single chunk.
        Only splits if text exceeds ~3000 chars (~750 tokens).
        """
        if len(text) < 3000:
            return [text]

        paragraphs = text.split("\n")
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para) // 4  # rough token estimate
            if current_len + para_len > target_tokens and current:
                chunks.append("\n".join(current))
                # Keep last paragraph as overlap
                current = current[-1:] if current else []
                current_len = len(current[0]) // 4 if current else 0
            current.append(para)
            current_len += para_len

        if current:
            chunks.append("\n".join(current))

        return chunks if chunks else [text]

    @lru_cache(maxsize=256)
    def _embed_query(self, query: str) -> list[float]:
        """Embed a search query with LRU caching."""
        return self._embedder.embed(query)
