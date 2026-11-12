"use client"

import {
  Search,
  Download,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@operation-room/components/ui/card"
import { Button } from "@operation-room/components/ui/button"
import { Badge } from "@operation-room/components/ui/badge"
import { Input } from "@operation-room/components/ui/input"
import type { QueryResult, SortDir } from "./types"

interface MagicQueryResultsProps {
  result: QueryResult
  processedRows: Record<string, string | number>[]
  pagedResultRows: Record<string, string | number>[]
  resultSearch: string
  setResultSearch: (v: string) => void
  resultPage: number
  setResultPage: (u: number | ((n: number) => number)) => void
  totalResultPages: number
  sortCol: string | null
  sortDir: SortDir
  handleSort: (col: string) => void
  copiedCell: string | null
  copyCell: (val: string, key: string) => void
  exportCSV: () => void
  resultRowsPerPage: number
}

export function MagicQueryResults({
  result,
  processedRows,
  pagedResultRows,
  resultSearch,
  setResultSearch,
  resultPage,
  setResultPage,
  totalResultPages,
  sortCol,
  sortDir,
  handleSort,
  copiedCell,
  copyCell,
  exportCSV,
  resultRowsPerPage,
}: MagicQueryResultsProps) {
  const summary = `${result.totalRows} row${result.totalRows === 1 ? "" : "s"} · ${result.executionTime}ms · ${result.columns.length} columns`

  return (
    <Card className="border shadow-none">
      <CardHeader className="px-4 py-3 space-y-1 border-b border-border/60">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="text-sm font-semibold">Results</CardTitle>
            <p className="text-[11px] text-muted-foreground mt-0.5 font-mono">{summary}</p>
            <p className="text-[10px] text-muted-foreground mt-1 max-w-prose">
              Rows come from Phase 4 committed data when an audit is set; the server applies safe filters derived from
              your SELECT (not full arbitrary SQL execution).
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="size-3 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Filter in page…"
                value={resultSearch}
                onChange={(e) => {
                  setResultSearch(e.target.value)
                  setResultPage(1)
                }}
                className="h-8 w-44 pl-8 text-[11px]"
              />
            </div>
            <Button variant="outline" size="sm" className="h-8 text-[11px] gap-1.5" onClick={exportCSV}>
              <Download className="size-3" />
              CSV
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="px-0 pb-0">
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="border-t border-b bg-muted/40">
                {result.columns.map((col) => (
                  <th
                    key={col}
                    className="px-3 py-2 text-left font-semibold text-muted-foreground uppercase tracking-wider text-[9px] cursor-pointer hover:bg-muted/60 select-none"
                    onClick={() => handleSort(col)}
                  >
                    <div className="flex items-center gap-1">
                      {col}
                      {sortCol === col ? (
                        sortDir === "asc" ? (
                          <ArrowUp className="size-2.5 text-primary" />
                        ) : (
                          <ArrowDown className="size-2.5 text-primary" />
                        )
                      ) : (
                        <ArrowUpDown className="size-2.5 text-muted-foreground/30" />
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pagedResultRows.map((row, ri) => (
                <tr key={ri} className="border-b border-border/50 hover:bg-muted/20">
                  {result.columns.map((col) => {
                    const val = String(row[col] ?? "")
                    const cellKey = `${ri}-${col}`
                    return (
                      <td
                        key={col}
                        className="px-3 py-2 font-mono whitespace-nowrap group cursor-pointer hover:bg-primary/[0.02]"
                        onClick={() => copyCell(val, cellKey)}
                        title="Click to copy"
                      >
                        <span className="flex items-center gap-1">
                          {col === "severity" ? (
                            <Badge
                              className={`text-[9px] px-1.5 py-0 h-4 font-bold ${
                                val === "ERROR"
                                  ? "bg-red-500/10 text-red-600 border border-red-300/30"
                                  : val === "WARN"
                                    ? "bg-amber-500/10 text-amber-600 border border-amber-300/30"
                                    : "bg-primary/10 text-primary border border-primary/20"
                              }`}
                            >
                              {val}
                            </Badge>
                          ) : col === "id" ? (
                            <span className="text-muted-foreground">{val}</span>
                          ) : col === "ip_address" ? (
                            <span className="text-primary">{val}</span>
                          ) : col === "event_template" ? (
                            <span className="truncate max-w-[280px]">{val}</span>
                          ) : (
                            <span className="truncate max-w-[200px]">{val}</span>
                          )}
                          {copiedCell === cellKey ? (
                            <Check className="size-2.5 text-emerald-600 shrink-0" />
                          ) : (
                            <Copy className="size-2.5 text-muted-foreground/0 group-hover:text-muted-foreground/40 shrink-0 transition-colors" />
                          )}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              ))}
              {pagedResultRows.length === 0 && (
                <tr>
                  <td colSpan={result.columns.length} className="px-3 py-8 text-center text-muted-foreground">
                    No matching rows.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between border-t px-3 py-2">
          <p className="text-[10px] text-muted-foreground">
            {processedRows.length > 0
              ? `Showing ${(resultPage - 1) * resultRowsPerPage + 1}–${Math.min(resultPage * resultRowsPerPage, processedRows.length)} of ${processedRows.length}`
              : "0 rows"}
          </p>
          <div className="flex items-center gap-1">
            <Button variant="outline" size="sm" className="h-7 w-7 p-0" disabled={resultPage === 1} onClick={() => setResultPage(1)}>
              <ChevronsLeft className="size-3" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              disabled={resultPage === 1}
              onClick={() => setResultPage((p) => p - 1)}
            >
              <ChevronLeft className="size-3" />
            </Button>
            <span className="text-[10px] text-muted-foreground px-2">
              {totalResultPages ? resultPage : 0} / {totalResultPages || 1}
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              disabled={resultPage >= totalResultPages}
              onClick={() => setResultPage((p) => p + 1)}
            >
              <ChevronRight className="size-3" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0"
              disabled={resultPage >= totalResultPages}
              onClick={() => setResultPage(totalResultPages)}
            >
              <ChevronsRight className="size-3" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
