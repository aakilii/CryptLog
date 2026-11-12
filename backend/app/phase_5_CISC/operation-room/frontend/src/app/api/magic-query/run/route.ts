import { NextRequest, NextResponse } from "next/server"
import { getMonolithApiBaseForPhase4 } from "@operation-room/lib/public-env"

interface ParsedLogRow {
  id: number
  timestamp: string
  event_template: string
  ip_address: string
  process_name: string
  user: string
  severity: string
  facility: string
  raw_log: string
}

const PARSED_LOGS: ParsedLogRow[] = Array.from({ length: 48 }, (_, i) => ({
  id: i + 1,
  timestamp: `2026-03-05T${String(8 + Math.floor(i / 6)).padStart(2, "0")}:${String((i * 7) % 60).padStart(2, "0")}:${String((i * 13) % 60).padStart(2, "0")}Z`,
  event_template: [
    "User <*> logged in from <*>",
    "Process <*> started on port <*>",
    "Connection refused from <*>:<*>",
    "File <*> modified by <*>",
    "Authentication failure for <*> from <*>",
    "Service <*> restarted successfully",
  ][i % 6],
  ip_address: `192.168.${1 + (i % 5)}.${10 + i}`,
  process_name: ["sshd", "nginx", "systemd", "crond", "auditd", "firewalld"][i % 6],
  user: ["root", "admin", "operator", "auditor", "system", "investigator"][i % 6],
  severity: ["INFO", "INFO", "WARN", "INFO", "ERROR", "INFO"][i % 6],
  facility: ["auth", "http", "system", "cron", "audit", "firewall"][i % 6],
  raw_log: `log-${i + 1}`,
}))

const UNSAFE = ["DELETE", "UPDATE", "DROP", "INSERT", "ALTER", "TRUNCATE", "CREATE", "REPLACE", "EXEC", "EXECUTE"]
const ALL_COLUMNS = ["id", "timestamp", "event_template", "ip_address", "process_name", "user", "severity", "facility", "raw_log"]

function apiBase(): string {
  return getMonolithApiBaseForPhase4()
}

function normalizeLiveRow(r: Record<string, unknown>): ParsedLogRow {
  return {
    id: Number(r.id) || 0,
    timestamp: String(r.timestamp ?? ""),
    event_template: String(r.event_template ?? ""),
    ip_address: String(r.ip_address ?? ""),
    process_name: String(r.process_name ?? ""),
    user: String(r.user ?? ""),
    severity: String(r.severity ?? ""),
    facility: String(r.facility ?? ""),
    raw_log: String(r.raw_log ?? ""),
  }
}

async function loadDataset(auditId: string | undefined): Promise<{
  rows: ParsedLogRow[]
  dataSource: "live" | "live_empty" | "mock" | "mock_fallback"
  detail?: string
}> {
  const id = (auditId || "").trim()
  if (!id) {
    return { rows: [...PARSED_LOGS], dataSource: "mock" }
  }

  try {
    const url = `${apiBase()}/api/phase4/parsed-logs?audit_id=${encodeURIComponent(id)}&limit=8000`
    const r = await fetch(url, { cache: "no-store" })
    if (!r.ok) {
      const t = await r.text().catch(() => "")
      return {
        rows: [...PARSED_LOGS],
        dataSource: "mock_fallback",
        detail: `Phase 4 API ${r.status}: ${t.slice(0, 200)}`,
      }
    }
    const j = (await r.json()) as { rows?: Record<string, unknown>[]; row_count?: number }
    const rawRows = Array.isArray(j.rows) ? j.rows : []
    if (rawRows.length === 0) {
      return { rows: [], dataSource: "live_empty", detail: "No committed Phase 2 rows in DuckDB for this audit_id." }
    }
    return { rows: rawRows.map(normalizeLiveRow), dataSource: "live" }
  } catch (e) {
    const msg = e instanceof Error ? e.message : "fetch failed"
    return {
      rows: [...PARSED_LOGS],
      dataSource: "mock_fallback",
      detail: msg,
    }
  }
}

function applySqlFilters(sql: string, rows: ParsedLogRow[]): ParsedLogRow[] {
  let out = [...rows]
  const whereIp = sql.match(/ip_address\s*=\s*'([^']+)'/i)?.[1]
  if (whereIp) out = out.filter((r) => r.ip_address === whereIp)

  const whereUser = sql.match(/\buser\s*=\s*'([^']+)'/i)?.[1]
  if (whereUser) out = out.filter((r) => r.user.toLowerCase() === whereUser.toLowerCase())

  const whereSeverity = sql.match(/severity\s*=\s*'([^']+)'/i)?.[1]
  if (whereSeverity) out = out.filter((r) => r.severity.toUpperCase() === whereSeverity.toUpperCase())

  const likeTerms = Array.from(
    sql.matchAll(/(?:event_template|raw_log)\s+LIKE\s+'%([^']+)%'/gi),
    (m) => m[1].toLowerCase(),
  )
  if (likeTerms.length) {
    out = out.filter((r) =>
      likeTerms.every(
        (t) => r.event_template.toLowerCase().includes(t) || r.raw_log.toLowerCase().includes(t),
      ),
    )
  }

  const limit = Number(sql.match(/LIMIT\s+(\d+)/i)?.[1] || out.length)
  out = out.slice(0, Math.max(0, limit))
  return out
}

export async function POST(request: NextRequest) {
  const start = performance.now()
  try {
    const body = await request.json()
    const sql = (body?.sql || "").toString().trim()
    const auditId = body?.audit_id != null ? String(body.audit_id).trim() : ""

    if (!sql) return NextResponse.json({ error: "SQL query is required" }, { status: 400 })

    const upper = sql.toUpperCase()
    for (const kw of UNSAFE) {
      if (new RegExp(`\\b${kw}\\b`).test(upper)) {
        return NextResponse.json({ error: `Unsafe SQL detected: ${kw}` }, { status: 400 })
      }
    }
    if (!upper.startsWith("SELECT") && !upper.startsWith("WITH")) {
      return NextResponse.json({ error: "Query must start with SELECT or WITH statement." }, { status: 400 })
    }

    const { rows: baseRows, dataSource, detail } = await loadDataset(auditId || undefined)
    const rows = applySqlFilters(sql, baseRows)

    const executionTime = Math.round((performance.now() - start) * 10) / 10
    return NextResponse.json({
      columns: ALL_COLUMNS,
      rows: rows.map((r) => ({ ...r })),
      executionTime,
      totalRows: rows.length,
      tablesUsed: ["parsed_logs"],
      dataSource,
      ...(detail ? { dataSourceDetail: detail } : {}),
    })
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Failed to execute query"
    return NextResponse.json({ error: message }, { status: 500 })
  }
}
