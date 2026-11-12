# VS Code AI Productivity Setup for Operation Room

This guide explains the project-specific setup for VS Code Chat Customizations, MCP, prompts, skills, and hooks.

## What Was Added

### 1. Workspace instructions
- .github/copilot-instructions.md
- .github/instructions/backend-python.instructions.md
- .github/instructions/frontend-next.instructions.md
- .github/instructions/docs-and-guides.instructions.md

### 2. Custom agents
- .github/agents/or-backend.agent.md
- .github/agents/or-frontend.agent.md
- .github/agents/or-investigation.agent.md

### 3. Prompt files
- .github/prompts/incident-kickoff.prompt.md
- .github/prompts/backend-fix.prompt.md
- .github/prompts/studio-v4-widget.prompt.md
- .github/prompts/release-readiness.prompt.md

### 4. Skills
- .github/skills/operation-room-dev-loop/SKILL.md
- .github/skills/forensic-report-workflow/SKILL.md
- .github/skills/mcp-ops/SKILL.md

### 5. Hooks
- .github/hooks/guardrails.json
- .github/hooks/scripts/hook_guard.py

### 6. MCP configuration
- .vscode/mcp.json

### 7. VS Code task shortcuts
- .vscode/tasks.json

### 8. VS Code extension baseline
- .vscode/extensions.json

### 9. Debug launch profiles
- .vscode/launch.json

### 10. Backend MCP runtime wiring
- operation-room/backend/app/main.py now:
  - imports MCP router
  - registers MCP tools at startup
  - starts/stops MCP server with app lifecycle
  - exposes endpoint under /mcp

## Why This Improves Productivity

- Faster execution: team can trigger standard workflows via slash prompts and skills.
- Consistent output quality: shared instructions and agents reduce drift in style and decisions.
- Safer automation: hooks add a defensive guard for destructive commands.
- Real tool integration: VS Code can call backend MCP tools through the configured MCP server.
- Less context switching: tasks.json provides one-click dev/test/lint/MCP health commands.

## How To Use

### Open chat customizations
1. Open Command Palette.
2. Run: Chat: Open Chat Customizations.
3. Confirm the new agents, skills, prompts, instructions, and hooks are visible.

### Use custom agents
- Select agent in chat input agent picker:
  - Operation Room Backend
  - Operation Room Frontend
  - Operation Room Investigation Review

### Use prompts
- Type / in chat and run:
  - /Operation Room Incident Kickoff
  - /Operation Room Backend Fix
  - /Studio V4 Widget Build
  - /Operation Room Release Readiness

### Use skills
- Type / in chat and run:
  - /operation-room-dev-loop
  - /forensic-report-workflow
  - /mcp-ops

### Start services quickly
Use VS Code tasks:
- backend: dev
- frontend: dev
- backend: test
- frontend: lint
- frontend: build
- mcp: health
- mcp: tools
- mcp: smoke
- verify: all
- release: readiness

Productivity defaults now included:
- backend tasks use the selected VS Code Python interpreter.
- backend tests run with PYTHONPATH=. for stable app.* imports.
- prompts route to the matching custom agent automatically.
- hook guard asks for confirmation before writes under operation-room/backend/data.
- workspace settings enforce consistent formatter, lint, and Python testing behavior.

### Recommended extensions
Open Extensions and install workspace recommendations from .vscode/extensions.json.

Core baseline includes:
- GitHub Copilot and Copilot Chat
- Python + Pylance + Black formatter + debugpy
- ESLint + Prettier + TypeScript tooling
- GitLens
- REST Client
- Markdown productivity tools

### Debug profiles
Use .vscode/launch.json profiles:
- backend: debug uvicorn
- frontend: launch browser

These profiles align to task and path defaults in this repository.

## MCP Setup Flow

1. Start backend task: backend: dev
2. Open Command Palette and run: MCP: List Servers
3. Confirm server operationRoom is available from .vscode/mcp.json
4. Start or restart the server from MCP UI if needed
5. Run tasks mcp: health, mcp: tools, and mcp: smoke

## Full Build Update Flow

For complete update cycles, run:
1. Develop:
  - backend: dev
  - frontend: dev
2. Verify:
  - verify: all
3. Build:
  - frontend: build
4. Release readiness:
  - release: readiness

This sequence standardizes development, validation, and release checks for the whole team.

Expected endpoints:
- http://localhost:8000/mcp/health
- http://localhost:8000/mcp/tools

## Team Adoption Checklist

- Commit .github and .vscode additions so all contributors get the same setup.
- Keep prompts and skills focused; update descriptions when workflows change.
- Add new skills only for repeatable, multi-step workflows.
- Keep hook scripts short and auditable.
- Review MCP logs in VS Code Output if tool discovery fails.

## Troubleshooting

### MCP server appears but no tools
- Ensure backend is running from operation-room/backend.
- Confirm app startup imported app.mcp.tools (wired in main.py).
- Run MCP: Reset Cached Tools and retry.

### backend: dev exits quickly with code 1
- If mcp: health still succeeds, port 8000 is already in use by another backend process.
- Stop the existing process or change the port in the task and .vscode/mcp.json together.
- Re-run backend: dev and then mcp: smoke.

### MCP trust prompt blocked usage
- Run MCP: Reset Trust.
- Re-approve workspace MCP server.

### Hooks not firing
- Confirm file exists at .github/hooks/guardrails.json.
- Check Output channel: GitHub Copilot Chat Hooks.

### Prompt or skill not showing
- Reopen Chat Customizations.
- Verify frontmatter name and description are present.

## Enhancement Ideas

- Add role-specific prompts for SOC analyst, incident manager, and legal reviewer.
- Add a backend smoke-test skill that runs health checks and selected tests.
- Add a release bundle skill that validates backend, frontend, MCP, and docs together.
