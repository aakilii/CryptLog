import type { Page } from "@/lib/app-context"

/** Primary shell route — bookmarkable page id (mirrors `Page` minus auth screens). */
export const APP_PAGE_QUERY = "page" as const

export type ShellPage = Exclude<Page, "login" | "register">

const SHELL: Set<string> = new Set([
  "dashboard",
  "ingestion",
  "parsing",
  "phase3",
  "ledger",
  "quarantine",
  "audit",
  "health",
  "settings",
])

export function parseShellPage(raw: string | null): ShellPage | null {
  if (!raw || !SHELL.has(raw)) return null
  return raw as ShellPage
}
