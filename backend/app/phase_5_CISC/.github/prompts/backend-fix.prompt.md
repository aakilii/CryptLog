---
name: "Operation Room Backend Fix"
description: "Implement and verify a backend fix in operation-room/backend with minimal risk, targeted tests, and clear validation output."
argument-hint: "Bug description, endpoint, and expected behavior"
agent: "Operation Room Backend"
model: "GPT-5 (copilot)"
tools: [read, search, edit, execute, todo]
---
Fix the backend issue using a minimal and safe change set.

Process:
1. Locate root cause with focused file reads and search.
2. Implement smallest correct patch.
3. Add or update targeted tests when feasible.
4. Run focused verification commands.
5. Summarize what changed, why, and how to verify.

Keep forensic data integrity constraints intact.
