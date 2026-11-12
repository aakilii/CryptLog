# CISC Workspace Instructions

## Workspace Focus
- The primary product is operation-room. Prioritize this folder unless the user asks otherwise.
- Treat archive_scripts and generated artifacts as read-only by default.

## Data and Evidence Safety
- Never modify or delete files under operation-room/backend/data unless the user explicitly requests it.
- Never rewrite historical forensic records to make tests pass.
- Preserve chain-of-custody behavior in backend changes.

## Backend Standards
- Keep FastAPI routes thin and move business logic into services.
- Prefer deterministic outputs, explicit validation, and defensive error handling.
- After Python backend changes, run targeted tests from operation-room/backend/tests when feasible.

## Frontend Standards
- Preserve Studio V4 canvas coordinate semantics and A4 page bounds.
- Reuse existing store and component patterns instead of introducing parallel state models.
- Avoid hardcoded backend URLs; use existing API wiring and environment variables.

## Documentation and Verification
- Update operation-room/docs when architecture or workflow behavior changes.
- In change summaries, include what changed, why it changed, and how to verify it.
