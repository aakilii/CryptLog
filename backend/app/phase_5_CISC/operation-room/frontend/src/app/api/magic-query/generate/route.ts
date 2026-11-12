import { NextRequest, NextResponse } from "next/server"
import { GoogleGenerativeAI } from "@google/generative-ai"

const SCHEMA = `
Table: parsed_logs
Columns:
  - id (INTEGER)
  - timestamp (TIMESTAMP)
  - event_template (TEXT)
  - ip_address (TEXT)
  - process_name (TEXT)
  - user (TEXT)
  - severity (TEXT)
  - facility (TEXT)
  - raw_log (TEXT)
  - normalized_fields (JSON)
`

const SYSTEM_PROMPT = `You convert natural language forensic questions into safe SQL.
Rules:
1) Output only a read-only SQL query.
2) Use only SELECT or WITH ... SELECT.
3) Query only table parsed_logs.
4) Allowed columns: id, timestamp, event_template, ip_address, process_name, user, severity, facility, raw_log, normalized_fields.
5) Use single quotes for strings.
6) If user asks for unknown fields, search with LIKE on event_template/raw_log.
Schema:
${SCHEMA}`

const UNSAFE = ["DELETE", "UPDATE", "DROP", "INSERT", "ALTER", "TRUNCATE", "CREATE", "REPLACE", "EXEC", "EXECUTE"]

function sanitizeGeneratedSql(sql: string): string {
  let cleaned = sql.trim()
  cleaned = cleaned.replace(/^```sql\s*/i, "").replace(/^```\s*/i, "").replace(/\s*```$/i, "")
  const upper = cleaned.toUpperCase()
  for (const kw of UNSAFE) {
    if (new RegExp(`\\b${kw}\\b`).test(upper)) {
      throw new Error(`Unsafe SQL detected: ${kw}`)
    }
  }
  if (!upper.startsWith("SELECT") && !upper.startsWith("WITH")) {
    throw new Error("Generated SQL must start with SELECT or WITH")
  }
  return cleaned.endsWith(";") ? cleaned : `${cleaned};`
}

function escapeSqlLike(s: string): string {
  return s.replace(/'/g, "''")
}

function fallbackSql(query: string): string {
  const q = query.trim().toLowerCase()
  if (!q) return "SELECT * FROM parsed_logs ORDER BY timestamp DESC LIMIT 50;"

  const ip = query.match(/\b(\d{1,3}(?:\.\d{1,3}){3})\b/)?.[1]
  if (ip) {
    return `SELECT * FROM parsed_logs WHERE ip_address = '${ip}' ORDER BY timestamp DESC LIMIT 100;`
  }

  if (q.includes("error") || q.includes("errors")) {
    return "SELECT * FROM parsed_logs WHERE severity = 'ERROR' ORDER BY timestamp DESC LIMIT 100;"
  }
  if (q.includes("warn") || q.includes("warning")) {
    return "SELECT * FROM parsed_logs WHERE severity = 'WARN' ORDER BY timestamp DESC LIMIT 100;"
  }
  if (q.includes("count") || q.includes("how many")) {
    return "SELECT severity, COUNT(*) AS event_count FROM parsed_logs GROUP BY severity ORDER BY event_count DESC;"
  }

  const terms = q
    .split(/\s+/)
    .map((w) => w.trim())
    .filter((w) => w.length > 1)
    .slice(0, 5)
    .map((w) => `(event_template LIKE '%${escapeSqlLike(w)}%' OR raw_log LIKE '%${escapeSqlLike(w)}%')`)

  if (!terms.length) return "SELECT * FROM parsed_logs ORDER BY timestamp DESC LIMIT 50;"
  return `SELECT * FROM parsed_logs WHERE ${terms.join(" AND ")} ORDER BY timestamp DESC LIMIT 100;`
}

export async function POST(request: NextRequest) {
  let input = ""
  try {
    const body = await request.json()
    input = (body?.query || "").toString()
    if (!input.trim()) {
      return NextResponse.json({ error: "Query is required" }, { status: 400 })
    }

    const apiKey = process.env.GEMINI_API_KEY
    if (!apiKey) {
      return NextResponse.json({ sql: fallbackSql(input), fallback: true })
    }

    const genAI = new GoogleGenerativeAI(apiKey)
    const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" })
    const result = await model.generateContent({
      contents: [{ role: "user", parts: [{ text: `${SYSTEM_PROMPT}\n\nUser query: ${input}` }] }],
    })
    const sql = sanitizeGeneratedSql(result.response.text())
    return NextResponse.json({ sql })
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : "Generator failed"
    return NextResponse.json(
      {
        sql: fallbackSql(input),
        fallback: true,
        fallbackReason: msg,
      },
      { status: 200 }
    )
  }
}
