---
name: "Operation Room Release Readiness"
description: "Run a release-readiness check across operation-room backend, frontend, docs, and MCP integration with prioritized findings."
argument-hint: "Release scope and risk priorities"
agent: "Operation Room Investigation Review"
model: "GPT-5 (copilot)"
tools: [read, search, execute, todo]
---
Perform a release-readiness review for the specified scope.

Check:
1. Runtime risks and regression-prone areas.
2. Missing tests or weak verification coverage.
3. API or data-contract mismatches.
4. Frontend-backend integration drift.
5. MCP and customization configuration health.

Output findings first, ordered by severity, then brief go/no-go guidance.
