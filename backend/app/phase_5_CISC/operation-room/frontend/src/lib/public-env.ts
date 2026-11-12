/**
 * Backend API origin for server-side routes (Magic Query → Phase 4 parsed-logs).
 */
function cleanEnv(val: string | undefined): string {
  if (val == null) return ""
  let t = val.trim()
  if (
    (t.startsWith('"') && t.endsWith('"')) ||
    (t.startsWith("'") && t.endsWith("'"))
  ) {
    t = t.slice(1, -1).trim()
  }
  return t
}

const apiUrlRaw = cleanEnv(process.env.NEXT_PUBLIC_API_URL) || "http://127.0.0.1:8000"

/** REST API origin (no trailing slash). */
export function getApiBaseUrl(): string {
  return apiUrlRaw.replace("://0.0.0.0", "://127.0.0.1").replace(/\/+$/, "")
}

/**
 * Phase 4 (`/api/phase4/parsed-logs`) is on the FastAPI monolith root, not under `/api/phase5`.
 * If `NEXT_PUBLIC_API_URL` ends with `/api/phase5` (common when aligning with Operation Room),
 * strip it so server-side Magic Query can reach Phase 4.
 */
export function getMonolithApiBaseForPhase4(): string {
  let b = getApiBaseUrl().replace(/\/+$/, "")
  const suffix = "/api/phase5"
  if (b.toLowerCase().endsWith(suffix)) {
    b = b.slice(0, -suffix.length)
  }
  return b.replace(/\/+$/, "") || "http://127.0.0.1:8000"
}
