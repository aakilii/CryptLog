---
name: "Studio V4 Widget Build"
description: "Design or fix a Studio V4 widget in operation-room/frontend with stable canvas behavior, inspector integration, and responsive UX."
argument-hint: "Widget purpose, data shape, and UI goals"
agent: "Operation Room Frontend"
model: "GPT-5 (copilot)"
tools: [read, search, edit, execute, todo]
---
Implement a Studio V4 widget or widget fix.

Requirements:
1. Respect existing canvas coordinates and page boundaries.
2. Reuse existing state/store patterns.
3. Handle loading, empty, and error states.
4. Confirm interactions work on desktop and mobile layouts.
5. Include a short verification checklist.

Return completed code changes and usage notes.
