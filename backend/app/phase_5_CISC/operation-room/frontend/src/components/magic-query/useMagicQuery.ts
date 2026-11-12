"use client"

import { useState, useCallback, useMemo, useRef } from "react"
import { useActiveAuditId } from "@operation-room/lib/use-active-audit-id"
import type { QueryResult, QueryHistoryEntry, SortDir } from "./types"
import { validateSQL } from "./sql-utils"

const RESULT_ROWS_PER_PAGE = 10

export function useMagicQuery() {
  const activeAuditId = useActiveAuditId()

  const [naturalQuery, setNaturalQuery] = useState("")
  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState<string | null>(null)
  const [usedFallback, setUsedFallback] = useState(false)
  const [fallbackReason, setFallbackReason] = useState<string | null>(null)

  const [sql, setSql] = useState("")
  const [insertField, setInsertField] = useState<string | null>(null)

  const [showConfirmation, setShowConfirmation] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [result, setResult] = useState<QueryResult | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [execError, setExecError] = useState<string | null>(null)

  const [resultSearch, setResultSearch] = useState("")
  const [resultPage, setResultPage] = useState(1)
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>(null)
  const [copiedCell, setCopiedCell] = useState<string | null>(null)

  const [history, setHistory] = useState<QueryHistoryEntry[]>([])
  const historyIdRef = useRef(0)

  const handleGenerateSQL = useCallback(async () => {
    if (!naturalQuery.trim()) return
    setGenerating(true)
    setGenerateError(null)
    setValidationError(null)
    setExecError(null)
    setResult(null)
    setShowConfirmation(false)
    setUsedFallback(false)
    setFallbackReason(null)

    try {
      const res = await fetch("/api/magic-query/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: naturalQuery.trim() }),
      })
      const data = await res.json()

      if (!res.ok) {
        setGenerateError(data.error || "Failed to generate SQL")
        setGenerating(false)
        return
      }

      setSql(data.sql || "")
      if (data.fallback) {
        setUsedFallback(true)
        setFallbackReason(data.fallbackReason || "Using local SQL generator.")
      }
      setGenerating(false)
    } catch (err: unknown) {
      setGenerateError(err instanceof Error ? err.message : "Network error")
      setGenerating(false)
    }
  }, [naturalQuery])

  const handleInsertField = useCallback((fieldName: string) => {
    setInsertField(fieldName)
    setTimeout(() => setInsertField(null), 50)
  }, [])

  const handleRunClick = useCallback(() => {
    const validation = validateSQL(sql)
    if (!validation.valid) {
      setValidationError(validation.error || "Invalid SQL")
      return
    }
    setValidationError(null)
    setShowConfirmation(true)
  }, [sql])

  const handleExecute = useCallback(async () => {
    setShowConfirmation(false)
    setExecuting(true)
    setExecError(null)
    setResultPage(1)
    setSortCol(null)
    setSortDir(null)
    setResultSearch("")

    try {
      const res = await fetch("/api/magic-query/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sql: sql.trim(), audit_id: activeAuditId || undefined }),
      })
      const data = await res.json()

      if (!res.ok) {
        setExecError(data.error || "Query execution failed")
        setExecuting(false)
        return
      }

      const queryResult: QueryResult = {
        columns: data.columns,
        rows: data.rows,
        executionTime: data.executionTime,
        totalRows: data.totalRows,
        tablesUsed: data.tablesUsed,
        dataSource: data.dataSource,
        dataSourceDetail: data.dataSourceDetail,
      }
      setResult(queryResult)
      setExecuting(false)

      historyIdRef.current += 1
      setHistory((prev) =>
        [
          {
            id: historyIdRef.current,
            query: naturalQuery || "(manual SQL)",
            sql: sql.trim(),
            rows: queryResult.totalRows,
            time: queryResult.executionTime,
            timestamp: new Date().toLocaleTimeString("en-GB", { hour12: false }),
          },
          ...prev,
        ].slice(0, 20),
      )
    } catch (err: unknown) {
      setExecError(err instanceof Error ? err.message : "Network error")
      setExecuting(false)
    }
  }, [sql, naturalQuery, activeAuditId])

  const handleReset = useCallback(() => {
    setSql("")
    setNaturalQuery("")
    setResult(null)
    setValidationError(null)
    setGenerateError(null)
    setExecError(null)
    setShowConfirmation(false)
    setExecuting(false)
    setResultSearch("")
    setResultPage(1)
    setSortCol(null)
    setSortDir(null)
    setUsedFallback(false)
    setFallbackReason(null)
  }, [])

  const processedRows = useMemo(() => {
    if (!result) return []
    let rows = [...result.rows]

    if (resultSearch.trim()) {
      const q = resultSearch.toLowerCase()
      rows = rows.filter((r) => Object.values(r).some((v) => String(v).toLowerCase().includes(q)))
    }

    if (sortCol && sortDir) {
      rows.sort((a, b) => {
        const aVal = a[sortCol] ?? ""
        const bVal = b[sortCol] ?? ""
        const cmp = String(aVal).localeCompare(String(bVal), undefined, { numeric: true })
        return sortDir === "asc" ? cmp : -cmp
      })
    }

    return rows
  }, [result, resultSearch, sortCol, sortDir])

  const totalResultPages = Math.ceil(processedRows.length / RESULT_ROWS_PER_PAGE)
  const pagedResultRows = processedRows.slice(
    (resultPage - 1) * RESULT_ROWS_PER_PAGE,
    resultPage * RESULT_ROWS_PER_PAGE,
  )

  const handleSort = useCallback(
    (col: string) => {
      if (sortCol === col) {
        if (sortDir === "asc") setSortDir("desc")
        else if (sortDir === "desc") {
          setSortCol(null)
          setSortDir(null)
        }
      } else {
        setSortCol(col)
        setSortDir("asc")
      }
      setResultPage(1)
    },
    [sortCol, sortDir],
  )

  const exportCSV = useCallback(() => {
    if (!result) return
    const header = result.columns.join(",")
    const rows = processedRows.map((r) =>
      result.columns.map((c) => `"${String(r[c] ?? "").replace(/"/g, '""')}"`).join(","),
    )
    const csv = [header, ...rows].join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `nflip-query-${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [result, processedRows])

  const copyCell = useCallback((val: string, key: string) => {
    navigator.clipboard.writeText(val)
    setCopiedCell(key)
    setTimeout(() => setCopiedCell(null), 1200)
  }, [])

  const loadFromHistory = useCallback((entry: QueryHistoryEntry) => {
    setNaturalQuery(entry.query)
    setSql(entry.sql)
    setResult(null)
  }, [])

  return {
    activeAuditId,
    naturalQuery,
    setNaturalQuery,
    generating,
    generateError,
    usedFallback,
    fallbackReason,
    sql,
    setSql,
    insertField,
    showConfirmation,
    setShowConfirmation,
    executing,
    result,
    validationError,
    execError,
    resultSearch,
    setResultSearch,
    resultPage,
    setResultPage,
    sortCol,
    sortDir,
    copiedCell,
    history,
    setHistory,
    processedRows,
    totalResultPages,
    pagedResultRows,
    resultRowsPerPage: RESULT_ROWS_PER_PAGE,
    handleGenerateSQL,
    handleInsertField,
    handleRunClick,
    handleExecute,
    handleReset,
    handleSort,
    exportCSV,
    copyCell,
    loadFromHistory,
  }
}
