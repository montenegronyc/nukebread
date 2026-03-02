"""Lightweight HTTP API for plugin-side RAG access.

The plugin (inside Nuke) cannot import psycopg2 or any pip packages,
so it reaches the pattern library via this HTTP API on port 9200.
Runs on a daemon thread alongside the MCP server.
"""

from __future__ import annotations

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

from nukebread.server.rag.store import CompPatternStore

logger = logging.getLogger("nukebread.rag.api")

_store: CompPatternStore | None = None


def _get_store() -> CompPatternStore:
    global _store
    if _store is None:
        _store = CompPatternStore()
    return _store


class _RAGHandler(BaseHTTPRequestHandler):
    """Handle RAG API requests."""

    def do_POST(self) -> None:
        try:
            body = self._read_body()
        except Exception:
            self._send_error(400, "Invalid request body")
            return

        if self.path == "/api/search":
            self._handle_search(body)
        elif self.path == "/api/save":
            self._handle_save(body)
        elif self.path == "/api/rate":
            self._handle_rate(body)
        elif self.path == "/api/import_nk":
            self._handle_import_nk(body)
        else:
            self._send_error(404, f"Unknown endpoint: {self.path}")

    def do_GET(self) -> None:
        if self.path == "/api/stats":
            self._handle_stats()
        elif self.path.startswith("/api/pattern/"):
            self._handle_get_pattern()
        elif self.path == "/api/patterns":
            self._handle_list_patterns()
        elif self.path == "/api/health":
            self._send_json({"status": "ok"})
        else:
            self._send_error(404, f"Unknown endpoint: {self.path}")

    # --- Handlers ---

    def _handle_search(self, body: dict) -> None:
        query = body.get("query", "")
        if not query:
            self._send_error(400, "Missing 'query' field")
            return

        store = _get_store()
        try:
            results = store.search(
                query=query,
                top_k=body.get("top_k", 5),
                category=body.get("category"),
                node_classes=body.get("node_classes"),
                include_graph=body.get("include_graph", False),
            )
            self._send_json({
                "results": [
                    {
                        "pattern_id": r.pattern_id,
                        "name": r.name,
                        "description": r.description,
                        "category": r.category,
                        "similarity": round(r.similarity, 4),
                        "node_count": r.node_count,
                        "avg_score": r.avg_score,
                        "graph_json": r.graph_json,
                    }
                    for r in results
                ],
                "count": len(results),
            })
        except Exception as exc:
            logger.exception("Search failed")
            self._send_error(500, str(exc))

    def _handle_save(self, body: dict) -> None:
        name = body.get("name", "")
        description = body.get("description", "")
        graph = body.get("graph")

        if not name or not graph:
            self._send_error(400, "Missing 'name' and/or 'graph' fields")
            return

        store = _get_store()
        try:
            pattern_id = store.save_pattern(
                name=name,
                description=description,
                graph_dict=graph,
                category=body.get("category"),
                use_cases=body.get("use_cases"),
                prerequisites=body.get("prerequisites"),
                source_script=body.get("source_script"),
                source_type=body.get("source_type", "manual"),
                tags=body.get("tags"),
            )
            self._send_json({"pattern_id": pattern_id, "status": "saved"})
        except Exception as exc:
            logger.exception("Save failed")
            self._send_error(500, str(exc))

    def _handle_rate(self, body: dict) -> None:
        pattern_id = body.get("pattern_id")
        success = body.get("success")

        if pattern_id is None or success is None:
            self._send_error(400, "Missing 'pattern_id' and/or 'success' fields")
            return

        store = _get_store()
        try:
            store.rate_pattern(
                pattern_id=pattern_id,
                success=success,
                score=body.get("score"),
                notes=body.get("notes"),
            )
            self._send_json({"status": "rated"})
        except Exception as exc:
            logger.exception("Rate failed")
            self._send_error(500, str(exc))

    def _handle_import_nk(self, body: dict) -> None:
        file_path = body.get("file_path", "")
        if not file_path:
            self._send_error(400, "Missing 'file_path' field")
            return

        from nukebread.server.rag.nk_parser import parse_nk_file

        store = _get_store()
        try:
            patterns = parse_nk_file(file_path)
            saved_ids = []
            for pattern in patterns:
                pid = store.save_pattern(
                    name=pattern["name"],
                    description=pattern["description"],
                    graph_dict=pattern["graph"],
                    category=pattern["category"],
                    source_script=file_path,
                    source_type="nk_import",
                )
                saved_ids.append(pid)

            self._send_json({
                "status": "imported",
                "patterns_saved": len(saved_ids),
                "pattern_ids": saved_ids,
            })
        except FileNotFoundError:
            self._send_error(404, f"File not found: {file_path}")
        except Exception as exc:
            logger.exception("Import failed")
            self._send_error(500, str(exc))

    def _handle_stats(self) -> None:
        store = _get_store()
        try:
            self._send_json(store.stats())
        except Exception as exc:
            logger.exception("Stats failed")
            self._send_error(500, str(exc))

    def _handle_get_pattern(self) -> None:
        try:
            pattern_id = int(self.path.split("/")[-1])
        except (ValueError, IndexError):
            self._send_error(400, "Invalid pattern ID")
            return

        store = _get_store()
        try:
            pattern = store.get_pattern(pattern_id)
            if pattern is None:
                self._send_error(404, f"Pattern {pattern_id} not found")
            else:
                self._send_json(pattern)
        except Exception as exc:
            logger.exception("Get pattern failed")
            self._send_error(500, str(exc))

    def _handle_list_patterns(self) -> None:
        store = _get_store()
        try:
            # Parse query params from path
            category = None
            limit = 50
            if "?" in self.path:
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(self.path).query)
                category = qs.get("category", [None])[0]
                if "limit" in qs:
                    limit = int(qs["limit"][0])

            patterns = store.list_patterns(category=category, limit=limit)
            self._send_json({"patterns": patterns, "count": len(patterns)})
        except Exception as exc:
            logger.exception("List patterns failed")
            self._send_error(500, str(exc))

    # --- Response helpers ---

    def _read_body(self) -> dict:
        length = int(self.headers.get("content-length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, data: Any) -> None:
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str) -> None:
        body = json.dumps({"error": message}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use Python logging instead of stderr."""
        logger.debug(format, *args)


def start_rag_api(port: int = 9200) -> HTTPServer | None:
    """Start the RAG HTTP API on a daemon thread.

    Returns the server instance, or None if the port is unavailable.
    """
    try:
        server = HTTPServer(("127.0.0.1", port), _RAGHandler)
    except OSError as exc:
        logger.warning("Could not start RAG API on port %d: %s", port, exc)
        return None

    thread = threading.Thread(
        target=server.serve_forever,
        name="rag-api",
        daemon=True,
    )
    thread.start()
    logger.info("RAG API started on http://127.0.0.1:%d", port)
    return server
