export const SQL_KEYWORDS = [
  "SELECT", "FROM", "WHERE", "AND", "OR", "NOT", "IN", "LIKE", "BETWEEN",
  "ORDER", "BY", "GROUP", "HAVING", "LIMIT", "OFFSET", "AS", "ON", "JOIN",
  "LEFT", "RIGHT", "INNER", "OUTER", "FULL", "CROSS", "UNION", "ALL",
  "DISTINCT", "COUNT", "SUM", "AVG", "MIN", "MAX", "NOW", "INTERVAL",
  "IS", "NULL", "TRUE", "FALSE", "CASE", "WHEN", "THEN", "ELSE", "END",
  "ASC", "DESC", "EXISTS", "CAST", "COALESCE", "EXTRACT", "DATE", "TIME",
  "TIMESTAMP", "WITH", "CURRENT_TIMESTAMP", "CURRENT_DATE",
]

export const UNSAFE_KEYWORDS = [
  "DELETE", "UPDATE", "DROP", "INSERT", "ALTER", "TRUNCATE", "CREATE", "REPLACE", "EXEC", "EXECUTE",
]

export const nerFields = [
  { name: "id", description: "Row ID (primary key)", type: "INTEGER" },
  { name: "timestamp", description: "ISO-8601 UTC timestamp", type: "TIMESTAMP" },
  { name: "event_template", description: "DRAIN3 event template", type: "TEXT" },
  { name: "ip_address", description: "IPv4 address", type: "TEXT" },
  { name: "process_name", description: "System process", type: "TEXT" },
  { name: "user", description: "System username", type: "TEXT" },
  { name: "severity", description: "INFO / WARN / ERROR", type: "TEXT" },
  { name: "facility", description: "Log facility", type: "TEXT" },
  { name: "raw_log", description: "Original log line", type: "TEXT" },
]

/** Short labels for quick-fill chips */
export const exampleQueries = [
  { label: "Logins from IP", query: "Show all login events from IP 192.168.1.22 in the last 24 hours" },
  { label: "Failed auth", query: "Find all failed authentication attempts grouped by user" },
  { label: "By severity", query: "Count events per severity level for today" },
  { label: "Errors & warnings", query: "Show all logs with severity ERROR or WARN" },
]
