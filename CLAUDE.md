# NukeBread — Claude × Nuke MCP Integration

## What This Is
An MCP server that gives Claude deep control over The Foundry's Nuke. Two halves:
1. **MCP Server** (`src/nukebread/server/`) — stdio subprocess, receives tool calls from Claude Code
2. **Nuke Plugin** (`src/nukebread/plugin/`) — runs inside Nuke, exposes local socket bridge

Shared types live in `src/nukebread/common/`.

## Architecture
```
Claude Code ──stdio──► MCP Server ──TCP socket──► Nuke Bridge (thread) ──executeInMainThread──► Nuke API
```

## Target Environment
- Nuke 17 (Python 3.11, PySide6)
- MCP transport: stdio
- Bridge transport: TCP socket on localhost (default port 9100)

## Project Structure
```
src/nukebread/
├── server/          # MCP server (runs as subprocess)
│   ├── main.py      # Entry point, tool registration
│   ├── nuke_client.py  # TCP client → Nuke bridge
│   └── tools/       # Tool definitions (graph_read, graph_write, vision, project, execution)
├── plugin/          # Nuke plugin (runs inside Nuke)
│   ├── bridge.py    # TCP server, dispatches to main thread
│   ├── serializer.py   # Graph ↔ JSON
│   ├── node_factory.py # Node creation with naming/undo
│   ├── frame_grabber.py # Frame capture → base64
│   ├── panel.py     # PySide6 chat panel
│   └── menu.py      # Nuke menu registration
└── common/          # Shared between server and plugin
    ├── types.py     # Pydantic models
    ├── protocol.py  # Bridge protocol
    └── constants.py # Ports, version, mappings
```

## Dev Conventions
- All tool inputs/outputs use Pydantic models from `common/types.py`
- Every Nuke API call goes through `nuke.executeInMainThread()`
- Multi-step operations wrapped in undo groups
- Every created node gets a descriptive name, never defaults
- Tests use `tests/mocks/nuke_mock.py` — no Nuke installation required
- Type hints everywhere, no docstrings on obvious methods

## Commands
- `uv run nukebread-server` — start MCP server
- `uv run pytest` — run tests
- `uv run pytest tests/test_serializer.py -v` — run specific test

## Implementation Status
- [x] Project scaffold and stubs
- [ ] Phase 1: Common types, bridge protocol, serializer
- [ ] Phase 2: MCP server with all tools wired through bridge
- [ ] Phase 3: Vision tools (frame grabber, comparison)
- [ ] Phase 4: Chat panel, templates, production features
