"""Chat backend that calls the Claude Messages API from within Nuke.

Uses only stdlib (urllib.request) so it works inside Nuke's embedded
Python without pip packages.  Executes tool calls against the shared
ToolRegistry, which dispatches to Nuke's main thread.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("nukebread.chat")

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
MAX_TOOL_ROUNDS = 10  # safety limit on tool-use loops

# Fallback system prompt if prompts/system_prompt.md can't be loaded.
_DEFAULT_SYSTEM_PROMPT = """\
You are NukeBridge, a compositor AI embedded inside The Foundry's Nuke.
You think in node graphs. When someone describes a look, you see the
comp tree. When they describe a problem, you trace the pipe. Be concise.
Be precise. Act fast. Bias toward action — the user can always undo.
Always read the graph before making changes. Wrap multi-step operations
in undo groups. Name every node descriptively.
"""


@dataclass
class ChatEvent:
    """Events yielded during a chat turn."""
    kind: str  # "text", "tool_call", "tool_result", "error"
    content: str
    tool_name: str = ""
    data: Any = None


class ChatBackend:
    """Manages conversation history and Claude API calls."""

    def __init__(self) -> None:
        self._messages: list[dict] = []
        self._system_prompt = self._load_system_prompt()
        self._api_key: str | None = None

    def clear(self) -> None:
        """Reset conversation history."""
        self._messages.clear()

    def send_message(self, user_text: str) -> list[ChatEvent]:
        """Send a user message and return all events from the response.

        This is a blocking call — run it in a background thread.
        It handles the tool-use loop internally, calling tools and
        re-submitting until Claude produces a final text response.
        """
        api_key = self._get_api_key()
        if not api_key:
            return [ChatEvent(
                kind="error",
                content="ANTHROPIC_API_KEY not set. Export it before launching Nuke.",
            )]

        from nukebread.plugin import get_registry
        registry = get_registry()

        # Add user message to history.
        self._messages.append({"role": "user", "content": user_text})

        events: list[ChatEvent] = []
        tools = registry.get_claude_tools()

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                response = self._call_api(api_key, tools)
            except Exception as exc:
                events.append(ChatEvent(kind="error", content=str(exc)))
                break

            stop_reason = response.get("stop_reason", "end_turn")
            content_blocks = response.get("content", [])

            # Build the assistant message for history.
            self._messages.append({"role": "assistant", "content": content_blocks})

            # Process content blocks.
            has_tool_use = False
            tool_results: list[dict] = []

            for block in content_blocks:
                if block["type"] == "text":
                    events.append(ChatEvent(kind="text", content=block["text"]))
                elif block["type"] == "tool_use":
                    has_tool_use = True
                    tool_id = block["id"]
                    tool_name = block["name"]
                    tool_input = block["input"]

                    events.append(ChatEvent(
                        kind="tool_call",
                        content=f"Using {tool_name}...",
                        tool_name=tool_name,
                        data=tool_input,
                    ))

                    # Execute the tool.
                    try:
                        result = registry.execute(tool_name, tool_input)
                        result_str = json.dumps(result, default=str)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result_str,
                        })
                        events.append(ChatEvent(
                            kind="tool_result",
                            content=f"{tool_name} completed",
                            tool_name=tool_name,
                            data=result,
                        ))
                    except Exception as exc:
                        error_str = f"Error: {exc}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": error_str,
                            "is_error": True,
                        })
                        events.append(ChatEvent(
                            kind="tool_result",
                            content=f"{tool_name} failed: {exc}",
                            tool_name=tool_name,
                        ))

            if has_tool_use and tool_results:
                # Send tool results back to Claude for the next round.
                self._messages.append({"role": "user", "content": tool_results})
                continue  # loop for next API call

            # No tool use — we're done.
            break

        return events

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _get_api_key(self) -> str | None:
        if self._api_key is None:
            self._api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        return self._api_key or None

    def _call_api(self, api_key: str, tools: list[dict]) -> dict:
        """Make a single Claude Messages API call."""
        body = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "system": self._system_prompt,
            "messages": self._messages,
        }
        if tools:
            body["tools"] = tools

        data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(
            API_URL,
            data=data,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Claude API error {exc.code}: {error_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Network error: {exc.reason}") from exc

    def _load_system_prompt(self) -> str:
        """Try to load prompts/system_prompt.md, fall back to default."""
        try:
            # Walk up from this file to find the project root.
            here = os.path.dirname(os.path.abspath(__file__))
            # plugin/ -> nukebread/ -> src/ -> project root
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(here)))
            prompt_path = os.path.join(project_root, "prompts", "system_prompt.md")
            if os.path.isfile(prompt_path):
                with open(prompt_path, "r") as f:
                    return f.read().strip()
        except Exception:
            pass
        return _DEFAULT_SYSTEM_PROMPT
