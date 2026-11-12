import { NextRequest, NextResponse } from "next/server"
import { GoogleGenerativeAI } from "@google/generative-ai"

/* ================================================================== */
/* PARSED LOGS SCHEMA — matches Phase-2 staging data                   */
/* ================================================================== */
const SCHEMA = `
Table: parsed_logs
Columns:
  - id (INTEGER, PRIMARY KEY, auto-increment)
  - timestamp (TIMESTAMP, ISO-8601 UTC format, e.g. '2026-03-05T08:00:00Z')
  - event_template (TEXT, DRAIN3-extracted template, e.g. 'User <*> logged in from <*>')
  - ip_address (TEXT, IPv4 address, e.g. '192.168.1.10')
  - process_name (TEXT, system process, values include: sshd, nginx, systemd, crond, auditd, firewalld)
  - user (TEXT, system username, values include: root, admin, operator, auditor, system, investigator)
  - severity (TEXT, log severity, values: INFO, WARN, ERROR)
  - facility (TEXT, log facility, values: auth, http, system, cron, audit, firewall)
  - raw_log (TEXT, original raw log line)
  - normalized_fields (JSON, contains severity and facility)

Total rows: 48
Date range: 2026-03-05
`

const SYSTEM_PROMPT = `You are a forensic SQL query generator for the NFLIP (National Forensic Log Intelligence Platform).
You convert natural language investigation queries into safe, read-only SQL.

STRICT RULES:
1. ONLY generate SELECT statements. Never generate DELETE, UPDATE, INSERT, DROP, ALTER, TRUNCATE, or any DDL/DML.
2. Always query from the "parsed_logs" table ONLY.
3. Use standard SQL syntax compatible with DuckDB.
4. Always use single quotes for string literals.
5. When the user asks about time, use the timestamp column with ISO-8601 format.
6. Return ONLY the SQL query, no explanations, no markdown, no code fences.
7. Use LIKE with wildcards for partial text matching on event_template or raw_log.
8. For "last N hours", use: timestamp > CURRENT_TIMESTAMP - INTERVAL 'N hours'
9. Always include ORDER BY when it makes sense (usually by timestamp DESC).

ACCURACY RULES (CRITICAL):
10. You MUST ONLY use columns that exist in the schema: id, timestamp, event_template, ip_address, process_name, user, severity, facility, raw_log, normalized_fields.
11. NEVER invent, assume, or fabricate columns that do not exist in the schema. There is NO "age", "port", "hostname", "status", "level", "source", "destination", "duration", "country", "location" or any other column not listed above.
12. If the user's query mentions a field or concept that does NOT map to any existing column, search for it as text within event_template or raw_log using LIKE '%keyword%'. Do NOT reinterpret the query as something else.
13. Do NOT map unrelated concepts together. For example, do NOT convert a number mentioned in one context (like "age more than 15") into a time interval or row count. Stay faithful to what the user literally asked.
14. If the user query contains a specific value (like a username, IP, number, keyword), use that EXACT value in the WHERE clause, not a different value.
15. When the user mentions a known column name (user, severity, ip_address, process_name, facility, timestamp), filter on that column directly.
16. When the user mentions an unknown attribute (e.g., "age", "country", "role"), search for it as text in event_template and raw_log using LIKE.

COLUMN REFERENCE:
- id: row identifier (integer)
- timestamp: when the event occurred (ISO-8601 timestamp)
- event_template: DRAIN3-extracted log template (text). Example values: 'User <*> logged in from <*>', 'Authentication failure for <*> from <*>'
- ip_address: IPv4 address (text). Example: '192.168.1.10'
- process_name: system process (text). Values: sshd, nginx, systemd, crond, auditd, firewalld
- user: system username (text). Values: root, admin, operator, auditor, system, investigator
- severity: log severity (text). Values: INFO, WARN, ERROR
- facility: log facility (text). Values: auth, http, system, cron, audit, firewall
- raw_log: original raw log line (text)
- normalized_fields: JSON blob with severity and facility

EXAMPLES:
User: "user age more than 15"
SQL: SELECT * FROM parsed_logs WHERE raw_log LIKE '%age%' AND raw_log LIKE '%15%' ORDER BY timestamp DESC

User: "login events from IP 192.168.1.22"
SQL: SELECT * FROM parsed_logs WHERE ip_address = '192.168.1.22' AND event_template LIKE '%logged in%' ORDER BY timestamp DESC

User: "failed authentication attempts"
SQL: SELECT * FROM parsed_logs WHERE event_template LIKE '%Authentication failure%' ORDER BY timestamp DESC

User: "show errors in last 2 hours"
SQL: SELECT * FROM parsed_logs WHERE severity = 'ERROR' AND timestamp > CURRENT_TIMESTAMP - INTERVAL '2 hours' ORDER BY timestamp DESC

User: "events by severity"
SQL: SELECT severity, COUNT(*) as event_count FROM parsed_logs GROUP BY severity ORDER BY event_count DESC

User: "all sshd activity"
SQL: SELECT * FROM parsed_logs WHERE process_name = 'sshd' ORDER BY timestamp DESC

DATABASE SCHEMA:
${SCHEMA}
`

export async function POST(request: NextRequest) {
  let queryText = ""
  try {
    const body = await request.json()
    const { query } = body
    queryText = query || ""

    if (!query || typeof query !== "string" || !query.trim()) {
      return NextResponse.json({ error: "Query is required" }, { status: 400 })
    }

    const apiKey = process.env.GEMINI_API_KEY
    if (!apiKey || apiKey === "your_gemini_api_key_here") {
      // Fallback: generate SQL locally if no API key configured
      return NextResponse.json({ sql: generateFallbackSQL(query), fallback: true })
    }

    const genAI = new GoogleGenerativeAI(apiKey)

    // Try models in order of preference — fall through if rate-limited
    const models = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    let lastError: any = null

    for (const modelName of models) {
      try {
        const model = genAI.getGenerativeModel({ model: modelName })
        const result = await model.generateContent({
          contents: [
            { role: "user", parts: [{ text: `${SYSTEM_PROMPT}\n\nUser query: ${query}` }] },
          ],
        })

        const response = result.response
        let sql = response.text().trim()

        // Strip any markdown code fences if Gemini adds them
        sql = sql.replace(/^```sql\s*/i, "").replace(/^```\s*/i, "").replace(/\s*```$/i, "")

        // Safety check: reject non-SELECT
        const upperSql = sql.toUpperCase().trim()
        const unsafeKeywords = ["DELETE", "UPDATE", "DROP", "INSERT", "ALTER", "TRUNCATE", "CREATE", "EXEC"]
        for (const kw of unsafeKeywords) {
          if (new RegExp(`\\b${kw}\\b`).test(upperSql)) {
            return NextResponse.json(
              { error: `Unsafe SQL detected: ${kw} keyword found. Only SELECT queries are allowed.` },
              { status: 400 }
            )
          }
        }

        console.log(`[Magic Query] Generated SQL using ${modelName}`)
        return NextResponse.json({ sql, model: modelName })
      } catch (err: any) {
        lastError = err
        console.log(`[Magic Query] ${modelName} failed: ${err.message?.includes("429") ? "rate-limited" : "error"}, trying next...`)
        continue
      }
    }

    // All models failed — throw to trigger fallback
    throw lastError
  } catch (error: any) {
    const isRateLimit = error.message?.includes("429")
    console.log(`[Magic Query] Gemini ${isRateLimit ? "rate-limited" : "unavailable"}, using local fallback generator`)
    // Fallback to local generator when Gemini fails (rate limit, network, etc.)
    const fallbackSql = generateFallbackSQL(queryText)
    return NextResponse.json({
      sql: fallbackSql,
      fallback: true,
      fallbackReason: error.message?.includes("429")
        ? "Gemini API rate limit exceeded. Using intelligent local generator."
        : "Gemini API unavailable. Using intelligent local generator.",
    })
  }
}

/* ================================================================== */
/* FALLBACK SQL GENERATOR (when no Gemini key)                         */
/* ================================================================== */
const KNOWN_COLUMNS = new Set(["id", "timestamp", "event_template", "ip_address", "process_name", "user", "severity", "facility", "raw_log", "normalized_fields"])
const KNOWN_USERS = ["root", "admin", "operator", "auditor", "system", "investigator"]
const KNOWN_SEVERITIES = ["info", "warn", "error"]
const KNOWN_PROCESSES = ["sshd", "nginx", "systemd", "crond", "auditd", "firewalld"]
const KNOWN_FACILITIES = ["auth", "http", "system", "cron", "audit", "firewall"]

function generateFallbackSQL(query: string): string {
  const q = query.toLowerCase().trim()
  const conditions: string[] = []
  let selectPart = "*"
  let orderBy = "ORDER BY timestamp DESC"
  let groupBy = ""
  let limit = ""

  // --- Extract numbers from the query ---
  const numberMatch = q.match(/\b(\d+)\b/)
  const extractedNumber = numberMatch ? numberMatch[1] : null

  // --- Extract IP addresses ---
  const ipMatch = query.match(/\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b/)

  // --- Detect time-based queries ---
  const timeMatch = q.match(/(?:last|past|recent)\s+(\d+)\s*(hour|minute|day|week|month)s?/)
  if (timeMatch) {
    conditions.push(`timestamp > CURRENT_TIMESTAMP - INTERVAL '${timeMatch[1]} ${timeMatch[2]}s'`)
  }

  // --- Detect severity filters ---
  const hasSeverityKeyword = q.includes("error") || q.includes("warn") || q.includes("info")
  const matchedSeverities = KNOWN_SEVERITIES.filter(s => q.includes(s))

  // --- Detect aggregation queries ---
  const isCountQuery = q.includes("count") || q.includes("how many") || q.includes("number of")
  const isGroupQuery = q.includes("group") || q.includes("per ") || q.includes("by ") || q.includes("breakdown")

  // --- Handle specific patterns ---

  // Login + IP
  if (q.includes("login") && ipMatch) {
    conditions.push(`ip_address = '${ipMatch[1]}'`)
    conditions.push(`event_template LIKE '%logged in%'`)
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // Login + IP (without login keyword)
  if (ipMatch) {
    conditions.push(`ip_address = '${ipMatch[1]}'`)
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // Failed auth
  if (q.includes("failed") && (q.includes("auth") || q.includes("login"))) {
    if (isGroupQuery || isCountQuery) {
      selectPart = "user, COUNT(*) as attempt_count, MIN(timestamp) as first_attempt, MAX(timestamp) as last_attempt"
      conditions.push(`event_template LIKE '%Authentication failure%'`)
      groupBy = "GROUP BY user"
      orderBy = "ORDER BY attempt_count DESC"
      return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
    }
    conditions.push(`event_template LIKE '%Authentication failure%'`)
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // Severity aggregation
  if ((isCountQuery || isGroupQuery) && q.includes("severity")) {
    return `SELECT severity, COUNT(*) as event_count\nFROM parsed_logs\nGROUP BY severity\nORDER BY event_count DESC;`
  }

  // Process aggregation
  if ((isCountQuery || isGroupQuery) && (q.includes("process") || q.includes("service"))) {
    return `SELECT process_name, COUNT(*) as event_count\nFROM parsed_logs\nGROUP BY process_name\nORDER BY event_count DESC;`
  }

  // User aggregation
  if ((isCountQuery || isGroupQuery) && q.includes("user")) {
    return `SELECT user, COUNT(*) as event_count\nFROM parsed_logs\nGROUP BY user\nORDER BY event_count DESC;`
  }

  // Multiple severities
  if (matchedSeverities.length > 1) {
    const sevList = matchedSeverities.map(s => `'${s.toUpperCase()}'`).join(", ")
    conditions.push(`severity IN (${sevList})`)
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // Single severity
  if (matchedSeverities.length === 1) {
    conditions.push(`severity = '${matchedSeverities[0].toUpperCase()}'`)
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // SSH activity
  if (q.includes("ssh")) {
    conditions.push(`process_name = 'sshd'`)
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // Firewall
  if (q.includes("firewall")) {
    conditions.push(`(facility = 'firewall' OR process_name = 'firewalld')`)
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // Known process names
  const matchedProcess = KNOWN_PROCESSES.find(p => q.includes(p))
  if (matchedProcess) {
    conditions.push(`process_name = '${matchedProcess}'`)
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // Known facility
  const matchedFacility = KNOWN_FACILITIES.find(f => q.includes(f) && f !== "system")
  if (matchedFacility) {
    conditions.push(`facility = '${matchedFacility}'`)
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // Known user names (exact match)
  const matchedUser = KNOWN_USERS.find(u => q.includes(u))
  if (matchedUser) {
    conditions.push(`user = '${matchedUser}'`)
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // Process/port queries
  if (q.includes("process") && (q.includes("port") || q.includes("start"))) {
    conditions.push(`event_template LIKE '%started on port%'`)
    return buildSQL("process_name, ip_address, timestamp, event_template", conditions, orderBy, groupBy, limit)
  }

  // Recent/latest
  if (q.includes("recent") || q.includes("latest") || q.includes("last")) {
    limit = "LIMIT 25"
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // All/everything
  if (q.includes("all") || q.includes("everything") || q.includes("show all")) {
    limit = "LIMIT 50"
    return buildSQL(selectPart, conditions, orderBy, groupBy, limit)
  }

  // --- FALLBACK: Search for unrecognized terms as text in raw_log and event_template ---
  // Extract meaningful words from the query (skip common stop words)
  const stopWords = new Set(["show", "find", "get", "list", "all", "the", "a", "an", "from", "to",
    "with", "where", "in", "on", "at", "for", "of", "and", "or", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
    "did", "will", "would", "shall", "should", "may", "might", "can", "could",
    "that", "this", "these", "those", "it", "its", "they", "them", "their",
    "me", "my", "than", "more", "less", "not", "no", "yes", "please", "query",
    "select", "logs", "log", "events", "event", "records", "data", "entries"])
  const words = q.split(/\s+/).filter(w => w.length > 1 && !stopWords.has(w))

  if (words.length > 0) {
    // Search for each meaningful word in raw_log and event_template
    const textConditions = words.map(w =>
      `(raw_log LIKE '%${w}%' OR event_template LIKE '%${w}%')`
    )
    conditions.push(textConditions.join(" AND "))
  }

  if (conditions.length === 0) {
    // Ultimate fallback
    return `SELECT *\nFROM parsed_logs\nORDER BY timestamp DESC\nLIMIT 50;`
  }

  return buildSQL(selectPart, conditions, orderBy, groupBy, "LIMIT 50")
}

function buildSQL(
  selectPart: string,
  conditions: string[],
  orderBy: string,
  groupBy: string,
  limit: string
): string {
  let sql = `SELECT ${selectPart}\nFROM parsed_logs`
  if (conditions.length > 0) {
    sql += `\nWHERE ${conditions.join("\n  AND ")}`
  }
  if (groupBy) sql += `\n${groupBy}`
  if (orderBy) sql += `\n${orderBy}`
  if (limit) sql += `\n${limit}`
  return sql + ";"
}
