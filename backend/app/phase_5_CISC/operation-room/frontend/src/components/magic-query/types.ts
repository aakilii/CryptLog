export type QueryDataSource = "live" | "live_empty" | "mock" | "mock_fallback"

export interface QueryResult {
  columns: string[]
  rows: Record<string, string | number>[]
  executionTime: number
  totalRows: number
  tablesUsed: string[]
  dataSource?: QueryDataSource
  dataSourceDetail?: string
}

export interface QueryHistoryEntry {
  id: number
  query: string
  sql: string
  rows: number
  time: number
  timestamp: string
}

export type SortDir = "asc" | "desc" | null
