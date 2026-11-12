# VS Code Complete Project Improvement Plan

## Objective

Standardize the full Operation Room build lifecycle with VS Code updates, plugin packs, MCP reliability, AI workflow governance, and forensic-quality gates.

This plan is implementation-focused and designed for team adoption.

## Scope

- Backend: FastAPI and MCP workflows in operation-room/backend
- Frontend: Next.js and Studio V4 workflows in operation-room/frontend
- Team workflows: prompts, skills, agents, hooks, tasks, debug profiles
- Documentation and release readiness checks

## Prerequisites

1. Workspace customizations are present in .github and .vscode.
2. Backend can be started from operation-room/backend.
3. MCP endpoint is reachable at http://127.0.0.1:8000/mcp.

## Phase 1: Workspace Foundation

### Actions

1. Keep MCP server contract in .vscode/mcp.json.
2. Keep one-click execution in .vscode/tasks.json.
3. Keep quote-safe MCP scripts in .vscode/scripts/mcp_tools_summary.py and .vscode/scripts/mcp_smoke.py.
4. Keep workspace defaults in .vscode/settings.json for formatter, lint, and Python testing consistency.
5. Install extension baseline from .vscode/extensions.json.
6. Use debug profiles from .vscode/launch.json.

### Expected Outcome

- Faster onboarding and fewer local environment mismatches.
- Stable MCP checks across Windows shells.

## Phase 2: Plugin Pack Rollout

### Core AI Pack

- github.copilot
- github.copilot-chat

### Backend Pack

- ms-python.python
- ms-python.vscode-pylance
- ms-python.black-formatter
- ms-python.debugpy
- humao.rest-client

### Frontend Pack

- dbaeumer.vscode-eslint
- esbenp.prettier-vscode
- ms-vscode.vscode-typescript-next

### Collaboration and Docs Pack

- eamodio.gitlens
- yzhang.markdown-all-in-one
- streetsidesoftware.code-spell-checker

### Rollout Rule

- Pilot with 2 developers for one sprint.
- Promote to team baseline after sprint review.
- Re-evaluate quarterly.

## Phase 3: End-to-End Build Flow

Use this standardized flow for every feature update:

1. Develop
- Run task: backend: dev
- Run task: frontend: dev

2. Verify
- Run task: verify: all
- This executes backend: test, frontend: lint, mcp: smoke in sequence.

3. Build
- Run task: frontend: build

4. Release Check
- Run task: release: readiness
- This executes verify: all, frontend: build, mcp: tools in sequence.

## Phase 4: AI Workflow Governance

### Customization Responsibilities

1. Global policy
- .github/copilot-instructions.md

2. File-type policy
- .github/instructions/backend-python.instructions.md
- .github/instructions/frontend-next.instructions.md
- .github/instructions/docs-and-guides.instructions.md

3. Role execution
- .github/agents/or-backend.agent.md
- .github/agents/or-frontend.agent.md
- .github/agents/or-investigation.agent.md

4. Task kickoffs
- .github/prompts/backend-fix.prompt.md
- .github/prompts/studio-v4-widget.prompt.md
- .github/prompts/incident-kickoff.prompt.md
- .github/prompts/release-readiness.prompt.md

5. Repeatable runbooks
- .github/skills/operation-room-dev-loop/SKILL.md
- .github/skills/mcp-ops/SKILL.md
- .github/skills/forensic-report-workflow/SKILL.md

6. Deterministic safety enforcement
- .github/hooks/guardrails.json
- .github/hooks/scripts/hook_guard.py

## Phase 5: Forensic Integrity Gates

1. Never modify operation-room/backend/data paths unless explicitly approved.
2. Keep route logic thin and business logic in services.
3. Enforce MCP readiness checks before MCP-dependent workflows.
4. Validate docs when architecture/workflow behavior changes.

## Phase 6: Team Operating Flow

### Backend Change Flow

1. Run /Operation Room Backend Fix prompt.
2. Execute operation-room-dev-loop skill.
3. Run backend: test and mcp: smoke.
4. Run /Operation Room Release Readiness for findings-first review.

### Frontend Change Flow

1. Run /Studio V4 Widget Build prompt.
2. Execute operation-room-dev-loop skill.
3. Run frontend: lint and verify: all.
4. Run /Operation Room Release Readiness.

### Investigation and Reporting Flow

1. Run /Operation Room Incident Kickoff prompt.
2. Execute forensic-report-workflow skill.
3. Run mcp: smoke before MCP-heavy analysis.
4. Verify release-readiness output before export workflows.

## Metrics and Improvement Cadence

Track weekly:

1. Time from task start to verified patch.
2. MCP success rate from mcp: smoke.
3. Percentage of work run via prompts and skills.
4. Hook intervention count and prevented risky actions.
5. Regression escapes after release readiness.

Run monthly calibration:

1. Remove stale prompts and skills.
2. Refine descriptions for better model discovery.
3. Update extension baseline if toolchain changed.

## Verification Checklist

1. Run backend: dev.
2. Run mcp: health.
3. Run mcp: tools.
4. Run mcp: smoke.
5. Run verify: all.
6. Run release: readiness.
7. Open Chat: Open Chat Customizations and verify agents, prompts, skills, instructions, and hooks are visible.

## Known Limits

1. If backend: dev exits with code 1 while mcp: health still works, port 8000 is already in use.
2. If MCP tools appear stale, run MCP: Reset Cached Tools.
3. If MCP trust blocks server usage, run MCP: Reset Trust.
