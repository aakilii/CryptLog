# Commands

## Backend Checks
- Install dependencies:
  - pip install -r operation-room/backend/requirements.txt
- Start backend API:
  - cd operation-room/backend
  - python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
- Run backend tests:
  - cd operation-room/backend
  - python -m pytest tests -q

## Frontend Checks
- Install dependencies:
  - cd operation-room/frontend
  - npm install
- Start frontend:
  - cd operation-room/frontend
  - npm run dev
- Run lint:
  - cd operation-room/frontend
  - npm run lint

## Integration Checks
- Backend health:
  - curl http://127.0.0.1:8000/api/health
- MCP health:
  - curl http://127.0.0.1:8000/mcp/health
- MCP tools:
  - curl http://127.0.0.1:8000/mcp/tools

## VS Code Task Shortcuts
- backend: dev
- backend: test
- frontend: dev
- frontend: lint
- mcp: health
- mcp: tools
- mcp: smoke
