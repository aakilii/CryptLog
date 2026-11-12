import { SQL_KEYWORDS, UNSAFE_KEYWORDS } from "./sql-constants"

export function highlightSQL(sql: string): string {
  let html = sql
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")

  html = html.replace(/'([^']*)'/g, '<span class="text-amber-500">\'$1\'</span>')
  html = html.replace(/\b(\d+)\b/g, '<span class="text-purple-400">$1</span>')

  const keywordPattern = new RegExp(`\\b(${SQL_KEYWORDS.join("|")})\\b`, "gi")
  html = html.replace(keywordPattern, '<span class="text-sky-400 font-bold">$1</span>')

  const unsafePattern = new RegExp(`\\b(${UNSAFE_KEYWORDS.join("|")})\\b`, "gi")
  html = html.replace(unsafePattern, '<span class="text-red-400 font-bold bg-red-950/50">$1</span>')

  html = html.replace(/(--.*$)/gm, '<span class="text-slate-500 italic">$1</span>')

  return html
}

export function validateSQL(sql: string): { valid: boolean; error?: string } {
  const trimmed = sql.trim()
  if (!trimmed) return { valid: false, error: "SQL query is empty." }

  const upper = trimmed.toUpperCase()

  for (const kw of UNSAFE_KEYWORDS) {
    if (new RegExp(`\\b${kw}\\b`, "i").test(upper)) {
      return {
        valid: false,
        error: `Only read-only queries are allowed. Detected: ${kw}`,
      }
    }
  }

  if (!upper.startsWith("SELECT") && !upper.startsWith("WITH")) {
    return { valid: false, error: "Query must start with SELECT or WITH." }
  }

  return { valid: true }
}
