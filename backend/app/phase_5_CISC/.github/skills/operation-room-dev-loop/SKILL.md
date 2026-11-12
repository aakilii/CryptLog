---
name: operation-room-dev-loop
description: "Run a disciplined implementation loop for operation-room backend and frontend: scope, patch, verify, and document."
argument-hint: "Changed area and target outcome"
user-invocable: true
---
# Operation Room Dev Loop

## When to Use
- Backend route or service implementation.
- Frontend Studio V4 updates.
- Cross-stack fixes that require API and UI verification.

## Procedure
1. Scope the change using focused search and targeted file reads.
2. Implement the smallest safe patch.
3. Run verification commands from [commands](./references/commands.md).
4. Update docs when behavior or workflow changes.
5. Summarize changes, why they were needed, and how they were verified.

## Output Checklist
- Changed files
- Verification commands run and outcomes
- Residual risks or follow-up checks
