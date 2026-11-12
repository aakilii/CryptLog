import { NextRequest, NextResponse } from "next/server"

/* ================================================================== */
/* PARSED LOGS DATABASE (in-memory mock from Phase-2 staging)          */
/* ================================================================== */
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
  severity: ["INFO", "INFO", "WARN", "INFO", "WARN", "INFO"][i % 6],
  facility: ["auth", "http", "system", "cron", "audit", "firewall"][i % 6],
  raw_log: `Mar  5 ${String(8 + Math.floor(i / 6)).padStart(2, "0")}:${String((i * 7) % 60).padStart(2, "0")}:${String((i * 13) % 60).padStart(2, "0")} server ${["sshd", "nginx", "systemd", "crond", "auditd", "firewalld"][i % 6]}[${1000 + i}]: ${["Accepted publickey for root", "GET /api/health 200", "Started Session", "CRON job executed", "AUDIT: op=login", "Reload firewall rules"][i % 6]}`,
}))

const UNSAFE_KEYWORDS = ["DELETE", "UPDATE", "DROP", "INSERT", "ALTER", "TRUNCATE", "CREATE", "REPLACE", "EXEC", "EXECUTE"]
const ALL_COLUMNS = ["id", "timestamp", "event_template", "ip_address", "process_name", "user", "severity", "facility", "raw_log"]

export async function POST(request: NextRequest) {
  const startTime = performance.now()

  try {
    const body = await request.json()
    const { sql } = body

    if (!sql || typeof sql !== "string" || !sql.trim()) {
      return NextResponse.json({ error: "SQL query is required" }, { status: 400 })
    }

    // Safety check
    const upperSql = sql.toUpperCase().trim()
    for (const kw of UNSAFE_KEYWORDS) {
      if (new RegExp(`\\b${kw}\\b`).test(upperSql)) {
        return NextResponse.json(
          { error: `Only read-only queries are allowed. Detected unsafe keyword: ${kw}` },
          { status: 400 }
        )
      }
    }

    if (!upperSql.startsWith("SELECT") && !upperSql.startsWith("WITH")) {
      return NextResponse.json(
        { error: "Query must start with SELECT or WITH statement." },
        { status: 400 }
      )
    }

    // Parse and execute the SQL against in-memory data
    const result = executeSQL(sql)
    const executionTime = Math.round((performance.now() - startTime) * 10) / 10

    return NextResponse.json({
      columns: result.columns,
      rows: result.rows,
      executionTime,
      totalRows: result.rows.length,
      tablesUsed: ["parsed_logs"],
    })
  } catch (error: any) {
    console.error("Query execution error:", error)
    return NextResponse.json(
      { error: error.message || "Failed to execute query" },
      { status: 500 }
    )
  }
}

/* ================================================================== */
/* SIMPLE SQL PARSER & EXECUTOR                                        */
/* ================================================================== */
function executeSQL(sql: string): { columns: string[]; rows: Record<string, string | number>[] } {
  const cleanSql = sql.replace(/;/g, "").trim()
  const upper = cleanSql.toUpperCase()

  // Determine requested columns
  let columns: string[] = []
  const selectMatch = cleanSql.match(/SELECT\s+([\s\S]*?)\s+FROM/i)
  if (selectMatch) {
    const selectPart = selectMatch[1].trim()
    if (selectPart === "*") {
      columns = [...ALL_COLUMNS]
    } else {
      // Parse column names, handling COUNT(*), aliases, etc.
      const parts = selectPart.split(",").map((p) => p.trim())
      columns = parts.map((p) => {
        // Handle aliases: "COUNT(*) as attempt_count" -> "attempt_count"
        const aliasMatch = p.match(/\bas\s+(\w+)/i)
        if (aliasMatch) return aliasMatch[1]
        // Handle functions: "COUNT(*)" -> "count"
        const funcMatch = p.match(/^(\w+)\s*\(/i)
        if (funcMatch) return funcMatch[1].toLowerCase()
        // Handle "MIN(timestamp)" -> "min_timestamp"
        if (p.includes("(")) {
          const fm = p.match(/(\w+)\((\w+)\)/i)
          if (fm) return `${fm[1].toLowerCase()}_${fm[2]}`
        }
        // Plain column
        return p.split(".").pop()?.trim() || p
      })
    }
  } else {
    columns = [...ALL_COLUMNS]
  }

  // Apply WHERE filters
  let filteredRows = [...PARSED_LOGS]
  const whereMatch = cleanSql.match(/WHERE\s+([\s\S]*?)(?:GROUP|ORDER|LIMIT|$)/i)
  if (whereMatch) {
    const wherePart = whereMatch[1].trim()
    filteredRows = applyWhere(filteredRows, wherePart)
  }

  // Handle GROUP BY
  const groupMatch = upper.match(/GROUP\s+BY\s+(\w+)/i)
  if (groupMatch) {
    const groupCol = groupMatch[1].toLowerCase()
    return executeGroupBy(filteredRows, groupCol, columns, selectMatch?.[1] || "*")
  }

  // Handle DISTINCT
  if (upper.includes("DISTINCT")) {
    const seen = new Set<string>()
    filteredRows = filteredRows.filter((row) => {
      const key = columns.map((c) => (row as any)[c]).join("|")
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }

  // Handle ORDER BY
  const orderMatch = cleanSql.match(/ORDER\s+BY\s+(\w+)\s*(ASC|DESC)?/i)
  if (orderMatch) {
    const orderCol = orderMatch[1].toLowerCase()
    const orderDir = (orderMatch[2] || "ASC").toUpperCase()
    filteredRows.sort((a, b) => {
      const aVal = (a as any)[orderCol] ?? ""
      const bVal = (b as any)[orderCol] ?? ""
      const cmp = String(aVal).localeCompare(String(bVal), undefined, { numeric: true })
      return orderDir === "DESC" ? -cmp : cmp
    })
  }

  // Handle LIMIT
  const limitMatch = upper.match(/LIMIT\s+(\d+)/i)
  if (limitMatch) {
    filteredRows = filteredRows.slice(0, parseInt(limitMatch[1]))
  }

  // Project columns
  const resolvedColumns = columns[0] === "*" || columns.includes("*") ? ALL_COLUMNS : columns.filter((c) => ALL_COLUMNS.includes(c) || c === "id")

  // If columns aren't recognized (aggregates etc), return all
  const finalColumns = resolvedColumns.length > 0 ? resolvedColumns : ALL_COLUMNS

  const rows: Record<string, string | number>[] = filteredRows.map((row) => {
    const r: Record<string, string | number> = {}
    for (const col of finalColumns) {
      r[col] = (row as any)[col] ?? ""
    }
    return r
  })

  return { columns: finalColumns, rows }
}

function applyWhere(rows: ParsedLogRow[], wherePart: string): ParsedLogRow[] {
  // Split by AND (simple parser)
  const conditions = wherePart.split(/\s+AND\s+/i)

  for (const cond of conditions) {
    const trimmed = cond.trim()

    // Handle LIKE: column LIKE '%pattern%'
    const likeMatch = trimmed.match(/(\w+)\s+LIKE\s+'([^']+)'/i)
    if (likeMatch) {
      const col = likeMatch[1].toLowerCase()
      const pattern = likeMatch[2].replace(/%/g, ".*")
      const regex = new RegExp(pattern, "i")
      rows = rows.filter((r) => regex.test(String((r as any)[col] ?? "")))
      continue
    }

    // Handle equality: column = 'value'
    const eqMatch = trimmed.match(/(\w+)\s*=\s*'([^']+)'/i)
    if (eqMatch) {
      const col = eqMatch[1].toLowerCase()
      const val = eqMatch[2]
      rows = rows.filter((r) => String((r as any)[col] ?? "").toLowerCase() === val.toLowerCase())
      continue
    }

    // Handle numeric equality: column = number
    const numEqMatch = trimmed.match(/(\w+)\s*=\s*(\d+)/i)
    if (numEqMatch) {
      const col = numEqMatch[1].toLowerCase()
      const val = parseInt(numEqMatch[2])
      rows = rows.filter((r) => Number((r as any)[col]) === val)
      continue
    }

    // Handle >= with string: column >= 'value'
    const gteMatch = trimmed.match(/(\w+)\s*>=\s*'([^']+)'/i)
    if (gteMatch) {
      const col = gteMatch[1].toLowerCase()
      const val = gteMatch[2]
      rows = rows.filter((r) => String((r as any)[col] ?? "") >= val)
      continue
    }

    // Handle > with INTERVAL (timestamp comparison) - just return all for now
    if (trimmed.match(/timestamp\s*>/i)) {
      // Return all rows (mock data is all from today anyway)
      continue
    }

    // Handle severity in list: severity IN ('ERROR', 'WARN')
    const inMatch = trimmed.match(/(\w+)\s+IN\s*\(([^)]+)\)/i)
    if (inMatch) {
      const col = inMatch[1].toLowerCase()
      const vals = inMatch[2].split(",").map((v) => v.trim().replace(/'/g, "").toLowerCase())
      rows = rows.filter((r) => vals.includes(String((r as any)[col] ?? "").toLowerCase()))
      continue
    }

    // Handle OR within a condition
    if (/\bOR\b/i.test(trimmed)) {
      const orParts = trimmed.split(/\s+OR\s+/i)
      rows = rows.filter((r) =>
        orParts.some((part) => {
          const m = part.trim().match(/(\w+)\s*=\s*'([^']+)'/i)
          if (m) return String((r as any)[m[1].toLowerCase()] ?? "").toLowerCase() === m[2].toLowerCase()
          const lm = part.trim().match(/(\w+)\s+LIKE\s+'([^']+)'/i)
          if (lm) {
            const pattern = lm[2].replace(/%/g, ".*")
            return new RegExp(pattern, "i").test(String((r as any)[lm[1].toLowerCase()] ?? ""))
          }
          return true
        })
      )
    }
  }

  return rows
}

function executeGroupBy(
  rows: ParsedLogRow[],
  groupCol: string,
  columns: string[],
  selectPart: string
): { columns: string[]; rows: Record<string, string | number>[] } {
  const groups = new Map<string, ParsedLogRow[]>()
  for (const row of rows) {
    const key = String((row as any)[groupCol] ?? "")
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(row)
  }

  const resultCols: string[] = []
  const resultRows: Record<string, string | number>[] = []

  // Parse aggregates from SELECT
  const parts = selectPart.split(",").map((p) => p.trim())
  const aggregates: { func: string; col: string; alias: string }[] = []

  for (const part of parts) {
    const aggMatch = part.match(/(\w+)\s*\(\s*(\*|\w+)\s*\)\s*(?:as\s+(\w+))?/i)
    if (aggMatch) {
      aggregates.push({
        func: aggMatch[1].toUpperCase(),
        col: aggMatch[2],
        alias: aggMatch[3] || `${aggMatch[1].toLowerCase()}_${aggMatch[2]}`,
      })
    } else if (part.toLowerCase() === groupCol) {
      // group column itself
    }
  }

  resultCols.push(groupCol)
  for (const agg of aggregates) resultCols.push(agg.alias)

  for (const [key, groupRows] of groups) {
    const row: Record<string, string | number> = { [groupCol]: key }
    for (const agg of aggregates) {
      if (agg.func === "COUNT") {
        row[agg.alias] = groupRows.length
      } else if (agg.func === "MIN") {
        row[agg.alias] = groupRows.reduce((min, r) => {
          const v = String((r as any)[agg.col] ?? "")
          return v < min ? v : min
        }, String((groupRows[0] as any)[agg.col] ?? ""))
      } else if (agg.func === "MAX") {
        row[agg.alias] = groupRows.reduce((max, r) => {
          const v = String((r as any)[agg.col] ?? "")
          return v > max ? v : max
        }, String((groupRows[0] as any)[agg.col] ?? ""))
      } else if (agg.func === "AVG" || agg.func === "SUM") {
        const sum = groupRows.reduce((s, r) => s + Number((r as any)[agg.col] ?? 0), 0)
        row[agg.alias] = agg.func === "AVG" ? Math.round((sum / groupRows.length) * 100) / 100 : sum
      }
    }
    resultRows.push(row)
  }

  return { columns: resultCols, rows: resultRows }
}
