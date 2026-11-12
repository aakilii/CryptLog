---
description: "Use when editing Python backend code in operation-room/backend. Covers FastAPI route boundaries, service-layer patterns, data integrity, and verification steps."
name: "Operation Room Backend Python"
applyTo: "operation-room/backend/**/*.py"
---
# Backend Python Instructions

- Keep route handlers in operation-room/backend/app/routes thin. Put core logic in operation-room/backend/app/services.
- Keep raw evidence immutable. Do not mutate source evidence records unless the user explicitly asks for a data migration.
- Prefer explicit request validation and typed responses.
- Add concise logging around branch decisions and error paths.
- Preserve existing API contracts unless the user asks for a breaking change.
- For changed behavior, add or update tests in operation-room/backend/tests when feasible.
- Use focused test runs before finalizing:
  - python -m pytest tests -q
