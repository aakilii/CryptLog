"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { Database, HardDrive, Timer, RefreshCw, Play, Loader2 } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  apiClient,
  type Phase3GraphqlQueryResponse,
  type Phase3HealthResponse,
} from "@/lib/api-client"
import { publicEnv } from "@/lib/public-env"
import { useApp } from "@/lib/app-context"

const DEMO_MODE = typeof process !== "undefined" && publicEnv.demoMode

const MOCK_HEALTH: Phase3HealthResponse = {
  ok: true,
  phase: 3,
  hot_db_path: "data/phase3_hot.duckdb",
  cold_dir: "data/phase3_cold",
  ttl_seconds: 30,
}

const MOCK_QUERY: Phase3GraphqlQueryResponse = {
  ok: true,
  status: "Rehydration Success",
  depth: 2,
  count: 2,
  data: [
    {
      Target_User: "unknown",
      Notes:
        "phase2_commit_complete audit_id=demo-audit staging_id=stg_demo_001 … [PII redacted for cold store]",
      Lineage: "stg_demo_001",
      created_at: new Date().toISOString(),
    },
    {
      Target_User: "admin",
      Notes: "Mar 19 10:01:02 host sshd[123]: Failed password … [redacted]",
      Lineage: "stg_demo_002",
      created_at: new Date().toISOString(),
    },
  ],
}

function truncate(s: string | undefined | null, max: number): string {
  if (s == null || s === "") return "—"
  return s.length <= max ? s : `${s.slice(0, max)}…`
}

export function Phase3Page() {
  const { activeAuditId } = useApp()
  const [targetUser, setTargetUser] = useState("unknown")
  const [health, setHealth] = useState<Phase3HealthResponse | null>(null)
  const [healthMock, setHealthMock] = useState(false)
  const [queryResult, setQueryResult] = useState<Phase3GraphqlQueryResponse | null>(null)
  const [queryMock, setQueryMock] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadingHealth, setLoadingHealth] = useState(false)
  const [loadingQuery, setLoadingQuery] = useState(false)

  const showMockBanner = healthMock || queryMock

  const loadHealth = useCallback(async () => {
    setLoadingHealth(true)
    setLoadError(null)
    try {
      const h = await apiClient.getPhase3Health()
      setHealth(h)
      setHealthMock(false)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Phase 3 health request failed"
      setLoadError(msg)
      setHealth(MOCK_HEALTH)
      setHealthMock(true)
    } finally {
      setLoadingHealth(false)
    }
  }, [])

  const runQuery = useCallback(async () => {
    const u = targetUser.trim()
    if (!u) {
      setLoadError("Target_User is required")
      return
    }
    setLoadingQuery(true)
    setLoadError(null)
    try {
      const q = await apiClient.phase3GraphqlQuery({
        Target_User: u,
        depth: 2,
        limit: 25,
        offset: 0,
      })
      setQueryResult(q)
      setQueryMock(false)
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Query failed"
      setLoadError(msg)
      const data = MOCK_QUERY.data.filter((r) => r.Target_User === u)
      setQueryResult({
        ...MOCK_QUERY,
        count: data.length,
        data,
      })
      setQueryMock(true)
    } finally {
      setLoadingQuery(false)
    }
  }, [targetUser])

  useEffect(() => {
    void loadHealth()
  }, [loadHealth])

  const queryRows = useMemo(() => queryResult?.data ?? [], [queryResult])

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-2xl font-bold tracking-tight text-slate-900">Hot / Cold gateway</div>
          <p className="text-sm text-slate-500 max-w-2xl mt-1">
            DuckDB hot tier + Parquet cold store. After Phase 2 commit, the webhook uses{" "}
            <code className="text-xs bg-muted px-1 rounded">Target_User: unknown</code> and{" "}
            <code className="text-xs bg-muted px-1 rounded">Lineage: &lt;staging_id&gt;</code>.
            Query cold rehydration by <code className="text-xs bg-muted px-1 rounded">Target_User</code>
            (try <code className="text-xs bg-muted px-1 rounded">unknown</code> or{" "}
            <code className="text-xs bg-muted px-1 rounded">admin</code> if you ingested via the E2E script).
          </p>
          {activeAuditId && (
            <p className="text-xs text-muted-foreground mt-2">
              Active pipeline audit:{" "}
              <code className="bg-muted px-1 rounded">{activeAuditId.slice(0, 10)}…</code> — Phase 3 rows are keyed by{" "}
              <code className="bg-muted px-1 rounded">Lineage = staging_id</code> from Phase 2 commits (not the audit UUID).
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {DEMO_MODE && (
            <Badge variant="secondary" className="text-xs">
              NEXT_PUBLIC_CSIC_DEMO_MODE
            </Badge>
          )}
          <Button variant="outline" size="sm" onClick={() => void loadHealth()} disabled={loadingHealth}>
            {loadingHealth ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            <span className="ml-2">Refresh health</span>
          </Button>
        </div>
      </div>

      {showMockBanner && (
        <Alert>
          <AlertTitle>Demo data</AlertTitle>
          <AlertDescription>
            Showing sample data because the Phase 3 API was unavailable or returned an error. Ensure the
            backend is running and optional deps are installed so /api/phase3/health and /api/phase3/graphql_query
            return 200.
            {loadError && (
              <span className="mt-2 block font-mono text-[11px] opacity-90">{loadError}</span>
            )}
          </AlertDescription>
        </Alert>
      )}

      {DEMO_MODE && !showMockBanner && (
        <p className="text-xs text-muted-foreground">
          NEXT_PUBLIC_CSIC_DEMO_MODE is set; live API responses are shown when requests succeed.
        </p>
      )}

      {loadError && !showMockBanner && (
        <Alert variant="destructive">
          <AlertTitle>Request error</AlertTitle>
          <AlertDescription>{loadError}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Hot DB</CardTitle>
            <Database className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-xs font-mono break-all text-muted-foreground">
              {health?.hot_db_path ?? (loadingHealth ? "…" : "—")}
            </p>
            {healthMock && <Badge variant="outline" className="mt-2 text-[10px]">mock</Badge>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cold directory</CardTitle>
            <HardDrive className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-xs font-mono break-all text-muted-foreground">
              {health?.cold_dir ?? (loadingHealth ? "…" : "—")}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Hot TTL</CardTitle>
            <Timer className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">
              {health != null ? `${health.ttl_seconds}s` : loadingHealth ? "…" : "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Rehydration query</CardTitle>
          <p className="text-xs text-muted-foreground">
            POST /api/phase3/graphql_query — cold Parquet scan filtered by Target_User.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-2 min-w-[200px] flex-1">
              <Label htmlFor="phase3-target">Target_User</Label>
              <Input
                id="phase3-target"
                value={targetUser}
                onChange={(e) => setTargetUser(e.target.value)}
                placeholder="unknown"
                autoComplete="off"
              />
            </div>
            <Button onClick={() => void runQuery()} disabled={loadingQuery}>
              {loadingQuery ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              <span className="ml-2">Run query</span>
            </Button>
          </div>

          {queryResult == null && !loadingQuery && (
            <p className="text-sm text-muted-foreground">Run a query to load rows from cold storage.</p>
          )}

          {queryResult != null && (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[100px]">User</TableHead>
                    <TableHead className="w-[140px]">Lineage</TableHead>
                    <TableHead className="w-[180px]">created_at</TableHead>
                    <TableHead>Notes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {queryRows.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-center text-muted-foreground text-sm">
                        No rows for this Target_User (count=0).
                      </TableCell>
                    </TableRow>
                  ) : (
                    queryRows.map((row, i) => (
                      <TableRow key={`${row.Lineage ?? i}-${i}`}>
                        <TableCell className="font-mono text-xs">{row.Target_User ?? "—"}</TableCell>
                        <TableCell className="font-mono text-xs">{truncate(row.Lineage, 24)}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {row.created_at ?? "—"}
                        </TableCell>
                        <TableCell className="text-xs max-w-[480px]">
                          <span className="line-clamp-3" title={row.Notes ?? ""}>
                            {truncate(row.Notes, 240)}
                          </span>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}

          {queryResult != null && (
            <p className="text-xs text-muted-foreground">
              status={queryResult.status} · depth={queryResult.depth} · count={queryResult.count}
              {queryMock && " · mock"}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
