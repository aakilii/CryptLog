import type { Page } from "@/lib/app-context"

/** Shell routes that use the gradient glass sidebar + top bar (same treatment as Main Dashboard). */
const SHELL_GLASS_CHROME: ReadonlySet<Page> = new Set([
  "dashboard",
  "ingestion",
  "ledger",
  "quarantine",
  "audit",
  "health",
  "parsing",
  "phase3",
  "settings",
])

export function isShellGlassChrome(page: Page): boolean {
  return SHELL_GLASS_CHROME.has(page)
}
