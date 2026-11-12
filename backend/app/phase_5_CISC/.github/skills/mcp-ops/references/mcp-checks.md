# MCP Checks

## Backend Readiness
- Start backend:
  - cd operation-room/backend
  - python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
- Check MCP health:
  - curl http://127.0.0.1:8000/mcp/health
- Check exposed tools:
  - curl http://127.0.0.1:8000/mcp/tools

## Task Shortcut Flow
- Run task: backend: dev
- Run task: mcp: health
- Run task: mcp: tools
- Run task: mcp: smoke

## VS Code Commands
- MCP: Open Workspace Folder MCP Configuration
- MCP: List Servers
- MCP: Reset Cached Tools
- MCP: Reset Trust

## Common Fixes
- If tools list is empty, ensure backend startup imports MCP tool modules.
- If backend: dev exits with code 1 but MCP health works, port 8000 is already occupied.
- If server fails to start, inspect Output panel channel for MCP server errors.
- If trust blocks startup, run MCP: Reset Trust and re-approve.
