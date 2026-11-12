"use client"

import { useState } from "react"
import Link from "next/link"
import {
  Sparkles,
  Play,
  RotateCcw,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Pencil,
  Terminal,
  Wand2,
  Info,
  Zap,
  History,
  Trash2,
  Columns3,
  ShieldAlert,
  Database,
  FileText,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@operation-room/components/ui/card"
import { Button } from "@operation-room/components/ui/button"
import { Badge } from "@operation-room/components/ui/badge"
import { Label } from "@operation-room/components/ui/label"
import { ScrollArea } from "@operation-room/components/ui/scroll-area"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@operation-room/components/ui/dialog"
import { Popover, PopoverContent, PopoverTrigger } from "@operation-room/components/ui/popover"
import { SqlCodeEditor } from "./SqlCodeEditor"
import { MagicQueryStatusBar } from "./MagicQueryStatusBar"
import { MagicQueryResults } from "./MagicQueryResults"
import { useMagicQuery } from "./useMagicQuery"
import { exampleQueries, nerFields } from "./sql-constants"
import { api } from "@operation-room/lib/api"

export function MagicQueryPage({
  embedded = false,
  caseId,
}: {
  embedded?: boolean
  /** When set (e.g. case import route), results can be imported into the case vault for OR modules. */
  caseId?: string
}) {
  const mq = useMagicQuery()
  const {
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
    resultRowsPerPage,
    handleGenerateSQL,
    handleInsertField,
    handleRunClick,
    handleExecute,
    handleReset,
    handleSort,
    exportCSV,
    copyCell,
    loadFromHistory,
  } = mq

  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [importSuccess, setImportSuccess] = useState<{ message: string; recordCount: number } | null>(null)

  const queriesRun = history.length

  const handleImportToCase = async () => {
    if (!caseId || !result?.rows?.length) return
    setImporting(true)
    setImportError(null)
    setImportSuccess(null)
    try {
      const rows = result.rows.map((r) => {
        const o: Record<string, string | number> = {}
        for (const [k, v] of Object.entries(r)) {
          o[k] = typeof v === "number" || typeof v === "string" ? v : String(v)
        }
        return o
      })
      const res = await api.importMagicQueryRows(caseId, {
        rows,
        audit_id: activeAuditId || undefined,
        justification: "Magic Query — import for investigation and reporting",
      })
      setImportSuccess({
        message: res?.message || "Imported.",
        recordCount: res?.record_count ?? rows.length,
      })
    } catch (e: unknown) {
      setImportError(e instanceof Error ? e.message : "Import failed")
    } finally {
      setImporting(false)
    }
  }

  const historyPopover = (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 text-[11px] gap-1.5 shrink-0">
          <History className="size-3.5" />
          History ({history.length})
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        <div className="flex items-center justify-between px-3 py-2 border-b">
          <span className="text-xs font-medium">Recent runs</span>
          {history.length > 0 && (
            <Button variant="ghost" size="sm" className="h-7 px-2" onClick={() => setHistory([])}>
              <Trash2 className="size-3" />
            </Button>
          )}
        </div>
        <ScrollArea className="max-h-56">
          {history.length === 0 ? (
            <p className="text-[11px] text-muted-foreground p-3">No queries yet.</p>
          ) : (
            <ul className="p-1">
              {history.map((h) => (
                <li key={h.id}>
                  <button
                    type="button"
                    className="w-full text-left rounded-md px-2 py-2 text-[11px] hover:bg-muted/80"
                    onClick={() => loadFromHistory(h)}
                  >
                    <span className="line-clamp-2 text-foreground">{h.query}</span>
                    <span className="text-[10px] text-muted-foreground mt-0.5 block">
                      {h.rows} rows · {h.time}ms
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  )

  return (
    <div className="flex flex-col min-h-0 h-full animate-in fade-in duration-300">
      <div
        className={`px-4 shrink-0 border-b border-border bg-card flex items-center gap-3 ${embedded ? "py-2 justify-end" : "pt-4 pb-3 justify-between"}`}
      >
        {!embedded && (
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex size-9 items-center justify-center bg-primary/10 shrink-0">
              <Wand2 className="size-4 text-primary" />
            </div>
            <div className="min-w-0">
              <h1 className="text-base font-bold text-foreground truncate">Magic Query</h1>
              <p className="text-[11px] text-muted-foreground truncate">
                Natural language → SQL (Gemini) → filtered rows from committed logs
              </p>
            </div>
          </div>
        )}
        {historyPopover}
      </div>

      <div className="px-4 py-3 shrink-0">
        <MagicQueryStatusBar activeAuditId={activeAuditId} result={result} queriesRun={queriesRun} />
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="px-4 pb-6 space-y-4 w-full max-w-5xl">
          <Card className="border shadow-none">
            <CardHeader className="px-4 py-3 space-y-0">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Sparkles className="size-4 text-primary" />
                  <CardTitle className="text-sm font-semibold">Ask a question</CardTitle>
                </div>
                <Badge variant="secondary" className="text-[10px] gap-1">
                  <Zap className="size-2.5" />
                  Gemini
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="px-4 pb-4 space-y-3">
              <div>
                <Label className="text-[10px] font-medium text-muted-foreground uppercase">Natural language</Label>
                <textarea
                  value={naturalQuery}
                  onChange={(e) => setNaturalQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault()
                      handleGenerateSQL()
                    }
                  }}
                  placeholder="e.g. Show failed logins from 192.168.1.22 in the last day"
                  rows={3}
                  className="mt-1.5 w-full resize-none border border-border bg-background rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {exampleQueries.map((eq) => (
                    <button
                      key={eq.label}
                      type="button"
                      onClick={() => setNaturalQuery(eq.query)}
                      className="text-[10px] px-2 py-1 rounded-full border border-border bg-muted/40 hover:bg-primary/10 hover:border-primary/30 transition-colors"
                    >
                      {eq.label}
                    </button>
                  ))}
                </div>
                <p className="text-[10px] text-muted-foreground mt-1.5">
                  <kbd className="px-1 py-0.5 bg-muted rounded text-[9px]">Ctrl+Enter</kbd> to generate SQL
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-[10px] text-muted-foreground">API key via server env</span>
                <Button
                  onClick={handleGenerateSQL}
                  disabled={generating || !naturalQuery.trim()}
                  size="sm"
                  className="h-9 gap-2"
                >
                  {generating ? (
                    <>
                      <Loader2 className="size-3.5 animate-spin" />
                      Generating…
                    </>
                  ) : (
                    <>
                      <Sparkles className="size-3.5" />
                      Generate SQL
                    </>
                  )}
                </Button>
              </div>

              {generateError && (
                <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50/60 p-3 text-[11px] text-red-700">
                  <AlertTriangle className="size-4 shrink-0 mt-0.5" />
                  {generateError}
                </div>
              )}

              {usedFallback && sql && (
                <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50/40 p-3 text-[11px] text-amber-800">
                  <Info className="size-4 shrink-0 mt-0.5" />
                  <span>{fallbackReason || "Local fallback SQL used."} Edit SQL below if needed.</span>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border shadow-none">
            <CardHeader className="px-4 py-3 space-y-0">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Terminal className="size-4 text-primary" />
                  <CardTitle className="text-sm font-semibold">SQL</CardTitle>
                  {sql && (
                    <Badge variant="outline" className="text-[9px] font-mono">
                      {sql.split("\n").length} lines
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button variant="outline" size="sm" className="h-8 text-[11px] gap-1">
                        <Columns3 className="size-3" />
                        Columns
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-72 p-0" align="end">
                      <div className="px-3 py-2 border-b text-[11px] font-medium">Insert into editor</div>
                      <ScrollArea className="max-h-52">
                        <div className="p-1">
                          {nerFields.map((field) => (
                            <button
                              key={field.name}
                              type="button"
                              title={field.description}
                              onClick={() => handleInsertField(field.name)}
                              className="w-full text-left rounded px-2 py-1.5 text-[11px] font-mono hover:bg-muted"
                            >
                              {field.name}
                              <span className="text-[9px] text-muted-foreground ml-2">{field.type}</span>
                            </button>
                          ))}
                        </div>
                      </ScrollArea>
                    </PopoverContent>
                  </Popover>
                  {sql && (
                    <>
                      <Button variant="outline" size="sm" className="h-8 text-[11px]" onClick={handleReset}>
                        <RotateCcw className="size-3" />
                        Reset
                      </Button>
                      <Button size="sm" className="h-8 text-[11px] gap-1" onClick={handleRunClick} disabled={executing}>
                        {executing ? <Loader2 className="size-3 animate-spin" /> : <Play className="size-3" />}
                        Run
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="px-4 pb-4 space-y-3">
              {!sql ? (
                <div className="flex flex-col items-center justify-center py-10 text-center border border-dashed rounded-md bg-muted/10">
                  <Terminal className="size-8 text-muted-foreground/30 mb-2" />
                  <p className="text-sm text-muted-foreground">Generate SQL from a question, or start manually.</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3 h-8 text-[11px]"
                    onClick={() => setSql("SELECT *\nFROM parsed_logs\nORDER BY timestamp DESC\nLIMIT 20;")}
                  >
                    <Pencil className="size-3" />
                    Starter SQL
                  </Button>
                </div>
              ) : (
                <SqlCodeEditor value={sql} onChange={setSql} insertField={insertField} />
              )}

              <p className="text-[10px] text-muted-foreground" title="Unsafe keywords are rejected server-side">
                <ShieldAlert className="inline size-3 align-text-bottom mr-1 text-amber-600/80" />
                Read-only SELECT / WITH. Tab inserts two spaces.
              </p>

              {validationError && (
                <div className="rounded-md border border-red-200 bg-red-50/80 p-3 text-[11px] text-red-700">{validationError}</div>
              )}
              {execError && (
                <div className="rounded-md border border-red-200 bg-red-50/60 p-3 text-[11px] text-red-700">{execError}</div>
              )}
            </CardContent>
          </Card>

          {executing && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
              <Loader2 className="size-4 animate-spin text-primary" />
              Loading rows…
            </div>
          )}

          {result && !executing && (
            <>
              <MagicQueryResults
                result={result}
                processedRows={processedRows}
                pagedResultRows={pagedResultRows}
                resultSearch={resultSearch}
                setResultSearch={setResultSearch}
                resultPage={resultPage}
                setResultPage={setResultPage}
                totalResultPages={totalResultPages}
                sortCol={sortCol}
                sortDir={sortDir}
                handleSort={handleSort}
                copiedCell={copiedCell}
                copyCell={copyCell}
                exportCSV={exportCSV}
                resultRowsPerPage={resultRowsPerPage}
              />

              {caseId && result.totalRows > 0 && (
                <Card className="border shadow-none border-primary/20 bg-primary/[0.03]">
                  <CardHeader className="px-4 py-3 space-y-1">
                    <CardTitle className="text-sm font-semibold">Use results in this case</CardTitle>
                    <p className="text-[11px] text-muted-foreground">
                      Import these rows into the case vault as <code className="text-[10px]">raw_events</code> (source{" "}
                      <code className="text-[10px]">MAGIC_QUERY</code>) so Timeline, analysis modules, and Report Studio
                      can use them.
                    </p>
                  </CardHeader>
                  <CardContent className="px-4 pb-4 space-y-3">
                    <Button
                      type="button"
                      disabled={importing}
                      onClick={handleImportToCase}
                      className="gap-2"
                    >
                      {importing ? (
                        <>
                          <Loader2 className="size-4 animate-spin" />
                          Importing…
                        </>
                      ) : (
                        <>
                          <Database className="size-4" />
                          Import results to case vault
                        </>
                      )}
                    </Button>
                    {importError && (
                      <div className="rounded-md border border-red-200 bg-red-50/80 px-3 py-2 text-[11px] text-red-700">
                        {importError}
                      </div>
                    )}
                    {importSuccess && (
                      <div className="space-y-2 rounded-md border border-emerald-200 bg-emerald-50/50 px-3 py-2 text-[11px] text-emerald-900">
                        <p className="font-medium">{importSuccess.message}</p>
                        <p className="text-muted-foreground">{importSuccess.recordCount} rows stored.</p>
                        <div className="flex flex-wrap gap-2 pt-1">
                          <Button variant="outline" size="sm" className="h-8 text-[11px] gap-1" asChild>
                            <Link href={`/cases/${caseId}/timeline`}>
                              Open Timeline
                            </Link>
                          </Button>
                          <Button variant="outline" size="sm" className="h-8 text-[11px] gap-1" asChild>
                            <Link href={`/cases/${caseId}/studio-v4`}>
                              <FileText className="size-3" />
                              Report Studio
                            </Link>
                          </Button>
                          <Button variant="outline" size="sm" className="h-8 text-[11px] gap-1" asChild>
                            <Link href={`/cases/${caseId}`}>Case dashboard</Link>
                          </Button>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </ScrollArea>

      <Dialog open={showConfirmation} onOpenChange={setShowConfirmation}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Run this query?</DialogTitle>
            <DialogDescription>
              The server loads committed Phase 4 rows for your audit (when set) and applies safe filters from your SELECT.
            </DialogDescription>
          </DialogHeader>
          <pre className="max-h-40 overflow-auto rounded-md border bg-[#0d1117] p-3 text-[11px] text-slate-300 font-mono whitespace-pre-wrap">
            {sql}
          </pre>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setShowConfirmation(false)}>
              Edit
            </Button>
            <Button onClick={handleExecute} className="gap-2">
              <CheckCircle2 className="size-4" />
              Confirm &amp; run
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
