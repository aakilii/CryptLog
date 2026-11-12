"use client"

import type { QueryResult } from "./types"

export function MagicQueryStatusBar({
  activeAuditId,
  result,
  queriesRun,
}: {
  activeAuditId: string | null
  result: QueryResult | null
  queriesRun: number
}) {
  const auditLabel = activeAuditId
    ? `${activeAuditId.slice(0, 8)}…`
    : "none"

  let sourceLabel = "—"
  if (result?.dataSource === "live") sourceLabel = "Phase 4 rows (committed)"
  else if (result?.dataSource === "live_empty") sourceLabel = "no rows for audit"
  else if (result?.dataSource === "mock_fallback") sourceLabel = "demo (API fallback)"
  else if (result?.dataSource === "mock") sourceLabel = "demo dataset"
  else if (activeAuditId) sourceLabel = "run to load"
  else sourceLabel = "demo (set audit for live)"

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-border bg-muted/30 px-3 py-2 text-[11px] text-muted-foreground">
      <span>
        <span className="font-medium text-foreground">Audit</span> {auditLabel}
      </span>
      <span className="text-border">·</span>
      <span>
        <span className="font-medium text-foreground">Source</span> {sourceLabel}
      </span>
      {result?.dataSourceDetail && (
        <>
          <span className="text-border">·</span>
          <span className="max-w-[min(100%,28rem)] truncate" title={result.dataSourceDetail}>
            {result.dataSourceDetail}
          </span>
        </>
      )}
      <span className="text-border">·</span>
      <span>
        <span className="font-medium text-foreground">Mode</span> read-only SELECT
      </span>
      <span className="text-border">·</span>
      <span>
        <span className="font-medium text-foreground">Queries</span> {queriesRun}
      </span>
    </div>
  )
}
