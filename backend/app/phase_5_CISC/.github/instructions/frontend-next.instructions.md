---
description: "Use when editing frontend code in operation-room/frontend. Covers Next.js routing, Studio V4 canvas behavior, state conventions, and safe UI changes."
name: "Operation Room Frontend Next"
applyTo: "operation-room/frontend/**/*.ts, operation-room/frontend/**/*.tsx, operation-room/frontend/**/*.js, operation-room/frontend/**/*.jsx"
---
# Frontend Next Instructions

- Keep Studio V4 layout behavior stable. Respect existing canvas coordinate and page-bound constraints.
- Reuse existing patterns in stores, hooks, and components before introducing new abstractions.
- Keep UI changes responsive and verify both desktop and mobile behavior.
- Avoid hardcoded backend origins in components. Prefer existing API client wiring and environment variables.
- For new feature UI, include loading, empty, and error states.
- Run lint checks for modified frontend code when feasible:
  - npm run lint
