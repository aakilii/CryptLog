---
name: "Operation Room Incident Kickoff"
description: "Build a structured investigation kickoff plan for operation-room using scenario analysis, required logs, module sequencing, and verification steps."
argument-hint: "Scenario description and known constraints"
agent: "Operation Room Investigation Review"
model: "GPT-5 (copilot)"
tools: [read, search, execute, todo]
---
Create a practical kickoff plan for this incident scenario.

Include:
1. Case understanding in plain language.
2. Required data sources and what each source proves.
3. Clarification questions needed before execution.
4. Module execution order in operation-room with reasons.
5. Verification checkpoints and likely failure points.
6. First 5 implementation actions the team should run.

Return a concise, execution-ready plan.
