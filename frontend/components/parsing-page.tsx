"use client"

import { useState, useEffect, useCallback, useMemo, useRef } from "react"
import {
  ShieldCheck,
  Search,
  Copy,
  Check,
  Loader2,
  AlertTriangle,
  FileWarning,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  PanelRightOpen,
  X,
  Anchor,
  Unlock,
  Languages,
  ScanSearch,
  Clock4,
  UserCheck,
  CheckCircle2,
  XCircle,
  Terminal,
  File,
  Eye,
  Pencil,
  Save,
  RotateCcw,
  ArrowRight,
  Shield,
  Hash,
  Network,
  HardDrive,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Progress } from "@/components/ui/progress"
import { apiClient } from "@/lib/api-client"
import { useApp } from "@/lib/app-context"

/* ================================================================== */
/* TYPES                                                               */
/* ================================================================== */
type PhaseStatus = "idle" | "active" | "success" | "error" | "awaiting_human"

interface LogEntry {
  time: string
  level: "INFO" | "WARN" | "ERROR" | "OK"
  message: string
}

interface ParsingPhase {
  id: string
  label: string
  subtitle: string
  description: string
  status: PhaseStatus
  progress: number
  logs: LogEntry[]
  stats: { label: string; value: string }[]
}

interface StagingRow {
  id: number
  staging_id: string
  timestamp: string
  event_template: string
  ip_address: string
  process_name: string
  user: string
  raw_log: string
  normalized_fields: string
}

interface DetectedEntity {
  type: string
  value: string
  confidence: number
}

interface ValidationFlag {
  type: "ambiguous_timestamp" | "suspicious_string" | "unknown_pattern"
  label: string
  description: string
}

interface Phase2StagingPreview {
  staging_id: string
  audit_id: string
  row_hash: string
  status: string
  decoded_payload: any | null
  decode_trace: any | null
  extracted_variables: Record<string, any> | null
  ner_tags: Record<string, any> | null
  normalized_timestamp: string | null
  human_overrides: Record<string, any> | null
  created_at: string | null
  immutable_pointer: string | null
  lineage?: any
  template?: any
  audit?: {
    audit_id: string
    filename: string
    sha256_hash: string
    source_ip: string | null
    upload_time: string | null
  }
}

interface Phase2ReviewRow {
  id: number
  staging_id: string
  line_number: number
  original: string
  decoded: string
  template: string
  variables: Record<string, any>
  ner_tags: Record<string, any>
  timestamp: string
  status: string
}

/* ================================================================== */
/* HELPERS                                                             */
/* ================================================================== */
function ts(): string {
  return new Date().toLocaleTimeString("en-GB", { hour12: false })
}


/* ================================================================== */
/* 6 PARSING PHASES (matches diagram: Nodes 1-6)                       */
/* ================================================================== */
function getInitialParsingPhases(): ParsingPhase[] {
  return [
    {
      id: "lineage",
      label: "Lineage Anchoring",
      subtitle: "Log Row Hash to DuckDB, Row ID to SQLite Audit Ledger, immutable pointer",
      description: "Anchors each log line via SHA-256 hash + byte offset, writes to DuckDB and SQLite for forensic chain.",
      status: "idle",
      progress: 0,
      logs: [],
      stats: [],
    },
    {
      id: "decoder",
      label: "Recursive De-obfuscation",
      subtitle: "Shannon entropy trigger, URL/Base64/Hex decoder ring, MAX_RECURSION_DEPTH=5",
      description: "Detects high-entropy obfuscation via Shannon analysis, then recursively decodes URL, Base64, and hex layers.",
      status: "idle",
      progress: 0,
      logs: [],
      stats: [],
    },
    {
      id: "translator",
      label: "Universal Translator (DRAIN3)",
      subtitle: "LRU Parse Cache, fast variable extraction, AI Parse Tree, template registry",
      description: "Extracts log templates via DRAIN3-style mining, isolates dynamic variables, and caches to template_registry.",
      status: "idle",
      progress: 0,
      logs: [],
      stats: [],
    },
    {
      id: "ner",
      label: "NER Tagging & Fallback Validation",
      subtitle: "Entity recognition, RE2 regex validation, Lock Tags, SQLi neutralization",
      description: "Tags IPs, emails, users, paths via NER model + regex. Validates with RE2, applies SQLi neutralization.",
      status: "idle",
      progress: 0,
      logs: [],
      stats: [],
    },
    {
      id: "chronograph",
      label: "Chronograph (Timeline Sync)",
      subtitle: "Timestamp extraction, ambiguity resolution, heuristic inference, ISO-8601 UTC",
      description: "Extracts timestamps, resolves DD/MM vs MM/DD ambiguity via heuristic engine, normalizes to ISO-8601 UTC.",
      status: "idle",
      progress: 0,
      logs: [],
      stats: [],
    },
    {
      id: "human_commit",
      label: "Human-in-the-Loop Commit",
      subtitle: "Web UI Preview, human overrides, final row hash, staging to DuckDB commit",
      description: "Officer reviews staged data, applies overrides. On commit: final hash written to audit ledger, data moves to DuckDB, Phase 3 webhook fires.",
      status: "idle",
      progress: 0,
      logs: [],
      stats: [],
    },
  ]
}

/* ================================================================== */
/* PHASE NODE NAMES (used by SSE -> phase index mapping)               */
/* ================================================================== */
const NODE_TO_PHASE_INDEX: Record<number, number> = { 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5 }

/* ================================================================== */
/* RAW EVIDENCE DATA (from API)                                       */
/* ================================================================== */

/* ================================================================== */
/* SMALL HELPER COMPONENTS                                             */
/* ================================================================== */
function PhaseStatusDot({ status }: { status: PhaseStatus }) {
  if (status === "idle") return <div className="size-2 bg-muted-foreground/30" />
  if (status === "active")
    return (
      <span className="relative flex size-2">
        <span className="absolute inline-flex size-full animate-ping bg-primary opacity-75" />
        <span className="relative inline-flex size-2 bg-primary" />
      </span>
    )
  if (status === "awaiting_human")
    return (
      <span className="relative flex size-2">
        <span className="absolute inline-flex size-full animate-ping bg-amber-500 opacity-75" />
        <span className="relative inline-flex size-2 bg-amber-500" />
      </span>
    )
  if (status === "success") return <div className="size-2 bg-success" />
  return <div className="size-2 bg-destructive" />
}

function PhaseStatusLabel({ status }: { status: PhaseStatus }) {
  if (status === "active")
    return (
      <Badge className="bg-primary/10 text-primary border border-primary/20 hover:bg-primary/10 text-xs gap-1.5 px-3 py-1">
        <Loader2 className="size-3.5 animate-spin" />
        RUNNING
      </Badge>
    )
  if (status === "awaiting_human")
    return (
      <Badge className="bg-amber-500/10 text-amber-600 border border-amber-500/20 hover:bg-amber-500/10 text-xs gap-1.5 px-3 py-1">
        <Eye className="size-3.5" />
        AWAITING REVIEW
      </Badge>
    )
  if (status === "success")
    return (
      <Badge className="bg-success/10 text-success border border-success/20 hover:bg-success/10 text-xs px-3 py-1">
        PASSED
      </Badge>
    )
  if (status === "error")
    return (
      <Badge className="bg-destructive/10 text-destructive border border-destructive/20 hover:bg-destructive/10 text-xs px-3 py-1">
        FAILED
      </Badge>
    )
  return (
    <Badge variant="outline" className="text-xs text-muted-foreground border-border px-3 py-1">
      PENDING
    </Badge>
  )
}

function LogLine({ entry }: { entry: LogEntry }) {
  const levelColors: Record<string, string> = {
    INFO: "text-primary",
    WARN: "text-amber-600",
    ERROR: "text-destructive",
    OK: "text-success",
  }
  return (
    <div className="flex gap-3 leading-5">
      <span className="text-muted-foreground shrink-0">{entry.time}</span>
      <span className={`font-bold shrink-0 w-12 ${levelColors[entry.level] || "text-muted-foreground"}`}>
        [{entry.level}]
      </span>
      <span className={`${entry.level === "ERROR" ? "text-destructive" : entry.level === "WARN" ? "text-amber-600" : "text-foreground"}`}>
        {entry.message}
      </span>
    </div>
  )
}

/* ================================================================== */
/* FULL PHASE CARD                                                     */
/* ================================================================== */
function FullPhaseCard({
  phase,
  index,
  onReviewClick,
}: {
  phase: ParsingPhase
  index: number
  onReviewClick?: () => void
}) {
  const icons = [Anchor, Unlock, Languages, ScanSearch, Clock4, UserCheck]
  const Icon = icons[index] || ShieldCheck
  const logEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (phase.status === "active" || phase.status === "success" || phase.status === "error" || phase.status === "awaiting_human") {
      logEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
    }
  }, [phase.logs.length, phase.status])

  if (phase.status === "idle") {
    return (
      <div className="border border-border bg-card p-6 opacity-40">
        <div className="flex items-center gap-4">
          <div className="flex size-12 items-center justify-center bg-muted">
            <Icon className="size-5 text-muted-foreground" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <span className="text-xs font-bold tracking-widest text-muted-foreground uppercase">Phase {index + 1}</span>
              <span className="text-sm font-semibold text-muted-foreground">{phase.label}</span>
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">{phase.description}</p>
          </div>
          <Badge variant="outline" className="ml-auto text-xs text-muted-foreground border-border px-3 py-1">PENDING</Badge>
        </div>
      </div>
    )
  }

  const borderAccent =
    phase.status === "success"
      ? "border-l-success"
      : phase.status === "error"
      ? "border-l-destructive"
      : phase.status === "awaiting_human"
      ? "border-l-amber-500"
      : "border-l-primary"

  return (
    <div className={`border border-border border-l-4 ${borderAccent} bg-card`}>
      {/* Phase Header */}
      <div className="flex items-center gap-4 border-b border-border p-5">
        <div
          className={`flex size-12 items-center justify-center ${
            phase.status === "success"
              ? "bg-success/10"
              : phase.status === "error"
              ? "bg-destructive/10"
              : phase.status === "awaiting_human"
              ? "bg-amber-500/10"
              : "bg-primary/10"
          }`}
        >
          {phase.status === "active" ? (
            <Loader2 className="size-6 animate-spin text-primary" />
          ) : phase.status === "success" ? (
            <CheckCircle2 className="size-6 text-success" />
          ) : phase.status === "awaiting_human" ? (
            <Eye className="size-6 text-amber-600" />
          ) : (
            <XCircle className="size-6 text-destructive" />
          )}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold tracking-widest text-muted-foreground uppercase">Phase {index + 1}</span>
            <span className="text-base font-bold text-foreground">{phase.label}</span>
          </div>
          <p className="mt-0.5 text-sm text-muted-foreground">{phase.subtitle}</p>
        </div>
        <PhaseStatusLabel status={phase.status} />
      </div>

      {/* Progress Bar */}
      <div className="px-5 pt-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-muted-foreground">Progress</span>
          <span className="font-mono text-sm font-bold text-foreground">{Math.round(phase.progress)}%</span>
        </div>
        <div className="h-3 w-full bg-muted overflow-hidden">
          <div
            className={`h-full transition-all duration-200 ${
              phase.status === "error" ? "bg-destructive"
              : phase.status === "success" ? "bg-success"
              : phase.status === "awaiting_human" ? "bg-amber-500"
              : "bg-primary"
            }`}
            style={{ width: `${phase.progress}%` }}
          />
        </div>
      </div>

      {/* Stats Row */}
      {phase.stats.length > 0 && (
        <div className="px-5 pt-4">
          <div className="grid grid-cols-4 gap-3">
            {phase.stats.map((stat) => (
              <div key={stat.label} className={`flex flex-col gap-1 border p-3 ${
                phase.status === "error" ? "border-destructive/20 bg-destructive/5"
                : phase.status === "awaiting_human" ? "border-amber-500/20 bg-amber-500/5"
                : "border-border bg-muted/30"
              }`}>
                <span className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">{stat.label}</span>
                <span className={`font-mono text-sm font-bold ${
                  phase.status === "error" ? "text-destructive"
                  : phase.status === "awaiting_human" ? "text-amber-700"
                  : "text-foreground"
                }`}>{stat.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Human Review Button - only for Phase 7 when awaiting */}
      {phase.status === "awaiting_human" && onReviewClick && (
        <div className="px-5 pt-4">
          <div className="border-2 border-dashed border-amber-400/50 bg-amber-50/30 p-5 flex flex-col items-center gap-3">
            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center bg-amber-500/10 rounded-full">
                <Eye className="size-5 text-amber-600" />
              </div>
              <div>
                <p className="text-sm font-bold text-foreground">Officer Review Required</p>
                <p className="text-xs text-muted-foreground">12 raw evidence records need human verification before commit</p>
              </div>
            </div>
            <Button
              onClick={onReviewClick}
              className="bg-amber-600 hover:bg-amber-700 text-white gap-2 h-11 px-8 text-sm font-bold shadow-lg shadow-amber-500/20 transition-all hover:shadow-amber-500/40 hover:scale-[1.02] active:scale-[0.98]"
            >
              <Eye className="size-4" />
              Review Raw Evidence
              <ArrowRight className="size-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Live Logs Terminal */}
      <div className="p-5">
        <div className="flex items-center gap-2 mb-2">
          <Terminal className="size-3.5 text-muted-foreground" />
          <span className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">Execution Log</span>
          {(phase.status === "active" || phase.status === "awaiting_human") && (
            <span className="relative flex size-2 ml-1">
              <span className={`absolute inline-flex size-full animate-ping ${phase.status === "awaiting_human" ? "bg-amber-500" : "bg-primary"} opacity-75`} />
              <span className={`relative inline-flex size-2 ${phase.status === "awaiting_human" ? "bg-amber-500" : "bg-primary"}`} />
            </span>
          )}
        </div>
        <div className="max-h-52 overflow-y-auto bg-foreground/[0.03] border border-border font-mono text-xs">
          <div className="p-3 flex flex-col gap-0.5">
            {phase.logs.map((log, i) => (
              <LogLine key={i} entry={log} />
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>
    </div>
  )
}

/* ================================================================== */
/* HUMAN REVIEW OVERLAY                                                */
/* ================================================================== */
function HumanReviewOverlay({
  onVerify,
  onClose,
}: {
  onVerify: () => void
  onClose: () => void
}) {
  const [data, setData] = useState<Phase2ReviewRow[]>([])
  const [editingCell, setEditingCell] = useState<{ row: number; col: keyof Phase2ReviewRow } | null>(null)
  const [editValue, setEditValue] = useState("")
  const [verifiedRows, setVerifiedRows] = useState<Set<number>>(new Set())
  const [searchQuery, setSearchQuery] = useState("")
  const [verifying, setVerifying] = useState(false)
  const [showSuccess, setShowSuccess] = useState(false)
  const [changeCount, setChangeCount] = useState(0)
  const editInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const load = async () => {
      // Prefer the latest ingestion audit persisted by Phase 1 UI.
      const raw = typeof window !== "undefined" ? localStorage.getItem("latest_ingestion_audit") : null
      const parsed = raw ? (JSON.parse(raw) as { auditId?: string }) : null
      const auditId = parsed?.auditId

      try {
        if (!auditId) {
          setData([])
          return
        }

        // Load Phase 2 staging previews (all node outputs) for this audit.
        // Some backends may not return previews via the audit endpoint yet; fall back to
        // querying staging IDs + fetching previews per entry.
        let previews: Phase2StagingPreview[] = []
        try {
          const res = await apiClient.getStagingPreviews(auditId, 200)
          previews = (res.previews || []) as unknown as Phase2StagingPreview[]
        } catch {
          previews = []
        }

        if (!previews.length) {
          const q = await apiClient.queryStaging({ audit_id: auditId, status: "pending", limit: 200, offset: 0 })
          const fetched: Phase2StagingPreview[] = []
          for (const e of q.entries || []) {
            try {
              fetched.push((await apiClient.getStagingPreview(e.staging_id)) as unknown as Phase2StagingPreview)
            } catch {
              // ignore individual row failures
            }
          }
          previews = fetched
        }

        const rows: Phase2ReviewRow[] = previews
          .map((p, idx) => {
            const vars = (p.extracted_variables || {}) as Record<string, any>
            const original = String(vars.original || "")
            const lineNumber = Number(vars.line_number || idx + 1)
            const decoded = String((p.decoded_payload as any)?.decoded || vars.decoded || "")
            const template = String((p.template as any)?.template || vars.template || "")
            const nerTags = (p.ner_tags || vars.ner_tags || {}) as Record<string, any>
            const tsVal = String(p.normalized_timestamp || vars.timestamp || "")

            return {
              id: idx + 1,
              staging_id: p.staging_id,
              line_number: Number.isFinite(lineNumber) ? lineNumber : idx + 1,
              original,
              decoded,
              template,
              variables: vars,
              ner_tags: nerTags,
              timestamp: tsVal,
              status: p.status || "pending",
            }
          })
          .sort((a, b) => a.line_number - b.line_number)

        setData(rows)
      } catch {
        setData([])
      }
    }

    void load()
  }, [])

  const editableColumns: (keyof Phase2ReviewRow)[] = ["original", "decoded", "template", "status"]

  const filteredData = useMemo(() => {
    if (!searchQuery.trim()) return data
    const q = searchQuery.toLowerCase()
    return data.filter(
      (r) =>
        r.original.toLowerCase().includes(q) ||
        r.decoded.toLowerCase().includes(q) ||
        r.template.toLowerCase().includes(q) ||
        r.staging_id.toLowerCase().includes(q) ||
        r.status.toLowerCase().includes(q)
    )
  }, [data, searchQuery])

  const startEdit = (rowId: number, col: keyof Phase2ReviewRow) => {
    if (!editableColumns.includes(col)) return
    const row = data.find((r) => r.id === rowId)
    if (!row) return
    setEditingCell({ row: rowId, col })
    setEditValue(typeof row[col] === "string" ? (row[col] as string) : JSON.stringify(row[col] ?? "", null, 2))
    setTimeout(() => editInputRef.current?.focus(), 50)
  }

  const saveEdit = () => {
    if (!editingCell) return
    setData((prev) =>
      prev.map((r) =>
        r.id === editingCell.row ? { ...r, [editingCell.col]: editValue } : r
      )
    )
    setChangeCount((c) => c + 1)
    setEditingCell(null)
    setEditValue("")
  }

  const cancelEdit = () => {
    setEditingCell(null)
    setEditValue("")
  }

  const toggleRowVerified = (id: number) => {
    setVerifiedRows((prev) => {
      const n = new Set(prev)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  }

  const verifyAll = () => {
    setVerifiedRows(new Set(data.map((r) => r.id)))
  }

  const allVerified = data.length > 0 && verifiedRows.size === data.length

  const handleVerifyAndCommit = async () => {
    setVerifying(true)
    try {
      const raw = typeof window !== "undefined" ? localStorage.getItem("latest_ingestion_audit") : null
      const parsed = raw ? (JSON.parse(raw) as { auditId?: string }) : null
      const auditId = parsed?.auditId
      if (!auditId) throw new Error("No audit ID found")

      const overrides: Record<string, any> = {}
      if (changeCount > 0) {
        for (const row of data) {
          overrides[row.staging_id] = {
            original: row.original,
            decoded: row.decoded,
            template: row.template,
            status: row.status,
          }
        }
      }
      await apiClient.commitStagingBatch(auditId, {
        human_overrides: changeCount > 0 ? overrides : undefined,
        confirm: true,
      })
      setShowSuccess(true)
      setTimeout(() => onVerify(), 1500)
    } catch (err) {
      console.error("Commit failed:", err)
      alert(err instanceof Error ? err.message : "Commit failed")
    } finally {
      setVerifying(false)
    }
  }

  const columns: { key: keyof Phase2ReviewRow; label: string; width: string; mono?: boolean }[] = [
    { key: "id", label: "#", width: "w-12" },
    { key: "line_number", label: "Line", width: "w-16", mono: true },
    { key: "original", label: "Node 1/Raw", width: "w-[520px]" },
    { key: "decoded", label: "Node 2/Decoded", width: "w-[520px]" },
    { key: "template", label: "Node 3/Template", width: "w-[520px]" },
    { key: "status", label: "Node 6/Status", width: "w-28" },
    { key: "timestamp", label: "Node 5/Timestamp", width: "w-44", mono: true },
    { key: "staging_id", label: "Staging ID", width: "w-56", mono: true },
  ]

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background/95 backdrop-blur-sm animate-in fade-in duration-300">
      {/* ── HEADER BAR ── */}
      <div className="border-b border-border bg-card px-6 py-4 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex size-10 items-center justify-center bg-amber-500/10">
              <Shield className="size-5 text-amber-600" />
            </div>
            <div>
              <h2 className="text-base font-bold text-foreground flex items-center gap-2">
                Human-in-Loop Evidence Review
                <Badge className="bg-amber-500/10 text-amber-600 border border-amber-500/20 hover:bg-amber-500/10 text-[10px]">
                  NODE 6
                </Badge>
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5">
                Review raw ingestion records. Edit flagged fields. Verify each row before committing.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {changeCount > 0 && (
              <Badge className="bg-primary/10 text-primary border border-primary/20 hover:bg-primary/10 text-xs gap-1 px-2.5">
                <Pencil className="size-3" />
                {changeCount} edit{changeCount > 1 ? "s" : ""} made
              </Badge>
            )}
            <Badge variant="outline" className="text-xs gap-1 px-2.5">
              <CheckCircle2 className="size-3" />
              {verifiedRows.size}/{data.length} verified
            </Badge>
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={onClose}>
              <X className="size-4 text-muted-foreground" />
            </Button>
          </div>
        </div>

        {/* Stats bar */}
        <div className="mt-3 grid grid-cols-6 gap-2">
          {[
            { icon: Hash, label: "Total Records", value: String(data.length) },
            { icon: AlertTriangle, label: "Flagged", value: String(data.filter((r) => r.status === "FLAGGED").length), warn: true },
            { icon: CheckCircle2, label: "Verified", value: `${verifiedRows.size}/${data.length}` },
            { icon: Pencil, label: "Edits Made", value: String(changeCount) },
            { icon: HardDrive, label: "Total Size", value: "4.82 GB" },
            { icon: Network, label: "Templates", value: String(new Set(data.map((r) => r.template || "∅")).size) },
          ].map((s) => (
            <div key={s.label} className={`flex items-center gap-2.5 border p-2.5 ${s.warn ? "border-amber-300/50 bg-amber-50/30" : "border-border bg-muted/30"}`}>
              <s.icon className={`size-3.5 shrink-0 ${s.warn ? "text-amber-600" : "text-muted-foreground"}`} />
              <div>
                <p className="text-[9px] font-semibold tracking-wider text-muted-foreground uppercase">{s.label}</p>
                <p className={`text-xs font-bold ${s.warn ? "text-amber-700" : "text-foreground"}`}>{s.value}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── TOOLBAR ── */}
      <div className="border-b border-border bg-card/50 px-6 py-2.5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search records..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 w-64 pl-8 text-[11px]"
            />
          </div>
          <Separator orientation="vertical" className="h-5" />
          <Button variant="outline" size="sm" className="h-8 text-[11px] gap-1.5" onClick={verifyAll}>
            <CheckCircle2 className="size-3.5" />
            Verify All
          </Button>
          <Button variant="outline" size="sm" className="h-8 text-[11px] gap-1.5" onClick={() => setVerifiedRows(new Set())}>
            <RotateCcw className="size-3.5" />
            Reset
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground">
            Click any <Pencil className="size-2.5 inline" /> cell to edit | Tick rows to verify
          </span>
        </div>
      </div>

      {/* ── TABLE ── */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <ScrollArea className="h-full">
          <div className="px-6 py-3">
            <div className="border border-border bg-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-[11px]">
                  <thead>
                    <tr className="bg-muted/60 border-b border-border">
                      <th className="px-2 py-2.5 text-center w-10">
                        <span className="text-[9px] font-bold tracking-widest text-muted-foreground uppercase">OK</span>
                      </th>
                      {columns.map((col) => (
                        <th key={col.key} className={`px-2.5 py-2.5 text-left font-bold text-muted-foreground uppercase tracking-wider text-[9px] ${col.width}`}>
                          <div className="flex items-center gap-1">
                            {col.label}
                            {editableColumns.includes(col.key) && <Pencil className="size-2 text-muted-foreground/50" />}
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredData.map((row) => {
                      const isVerified = verifiedRows.has(row.id)
                      const isFlagged = row.status === "FLAGGED"
                      return (
                        <tr
                          key={row.id}
                          className={`border-b border-border/50 transition-all duration-200 ${
                            isVerified
                              ? "bg-success/[0.03] hover:bg-success/[0.06]"
                              : isFlagged
                              ? "bg-amber-50/40 hover:bg-amber-50/70"
                              : "hover:bg-muted/30"
                          }`}
                        >
                          <td className="px-2 py-1.5 text-center">
                            <button
                              onClick={() => toggleRowVerified(row.id)}
                              className={`inline-flex size-5 items-center justify-center border-2 transition-all duration-200 ${
                                isVerified
                                  ? "bg-success border-success text-white scale-110"
                                  : "border-border bg-card hover:border-primary hover:scale-105"
                              }`}
                            >
                              {isVerified && <Check className="size-3" />}
                            </button>
                          </td>
                          {columns.map((col) => {
                            const isEditing = editingCell?.row === row.id && editingCell?.col === col.key
                            const isEditable = editableColumns.includes(col.key)
                            const cellVal = String(row[col.key])

                            if (isEditing) {
                              return (
                                <td key={col.key} className="px-1 py-1">
                                  <div className="flex items-center gap-1">
                                    <Input
                                      ref={editInputRef}
                                      value={editValue}
                                      onChange={(e) => setEditValue(e.target.value)}
                                      onKeyDown={(e) => {
                                        if (e.key === "Enter") saveEdit()
                                        if (e.key === "Escape") cancelEdit()
                                      }}
                                      className="h-6 text-[10px] font-mono px-1.5 border-primary ring-1 ring-primary/30"
                                    />
                                    <Button variant="ghost" size="sm" className="h-5 w-5 p-0 shrink-0" onClick={saveEdit}>
                                      <Save className="size-3 text-success" />
                                    </Button>
                                    <Button variant="ghost" size="sm" className="h-5 w-5 p-0 shrink-0" onClick={cancelEdit}>
                                      <X className="size-3 text-muted-foreground" />
                                    </Button>
                                  </div>
                                </td>
                              )
                            }

                            if (col.key === "status") {
                              return (
                                <td
                                  key={col.key}
                                  className={`px-2.5 py-1.5 ${isEditable ? "cursor-pointer" : ""}`}
                                  onDoubleClick={() => isEditable && startEdit(row.id, col.key)}
                                >
                                  <Badge className={`text-[9px] px-1.5 py-0 h-4 font-bold ${
                                    cellVal === "FLAGGED"
                                      ? "bg-amber-500/10 text-amber-700 border border-amber-400/30 hover:bg-amber-500/10"
                                      : "bg-success/10 text-success border border-success/30 hover:bg-success/10"
                                  }`}>
                                    {cellVal}
                                  </Badge>
                                </td>
                              )
                            }

                            if (col.key === "staging_id" || col.key === "timestamp") {
                              return (
                                <td
                                  key={col.key}
                                  className={`px-2.5 py-1.5 font-mono text-[10px] ${isEditable ? "cursor-pointer group" : ""}`}
                                  onDoubleClick={() => isEditable && startEdit(row.id, col.key)}
                                  title={cellVal}
                                >
                                  <span className="text-muted-foreground">{cellVal.slice(0, 12)}...{cellVal.slice(-6)}</span>
                                  {isEditable && <Pencil className="size-2.5 text-muted-foreground/0 group-hover:text-muted-foreground/60 inline ml-1 transition-colors" />}
                                </td>
                              )
                            }

                            return (
                              <td
                                key={col.key}
                                className={`px-2.5 py-1.5 ${col.mono ? "font-mono text-[10px]" : ""} ${isEditable ? "cursor-pointer group" : ""} whitespace-nowrap`}
                                onDoubleClick={() => isEditable && startEdit(row.id, col.key)}
                              >
                                <span>{cellVal}</span>
                                {isEditable && <Pencil className="size-2.5 text-muted-foreground/0 group-hover:text-muted-foreground/60 inline ml-1 transition-colors" />}
                              </td>
                            )
                          })}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </ScrollArea>
      </div>

      {/* ── BOTTOM ACTION BAR ── */}
      <div className="border-t border-border bg-card px-6 py-4 shrink-0">
        {showSuccess ? (
          <div className="flex items-center justify-center gap-3 py-1">
            <CheckCircle2 className="size-5 text-success" />
            <span className="text-sm font-bold text-success">Evidence verified and committed. Transitioning to staging view...</span>
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">{verifiedRows.size}</span> of <span className="font-semibold text-foreground">{data.length}</span> records verified
              </div>
              <div className="h-2 w-48 bg-muted overflow-hidden">
                <div
                  className="h-full bg-success transition-all duration-500"
                  style={{ width: `${(verifiedRows.size / Math.max(data.length, 1)) * 100}%` }}
                />
              </div>
              {changeCount > 0 && (
                <span className="text-xs text-primary font-medium">{changeCount} field{changeCount > 1 ? "s" : ""} edited by officer</span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" className="h-9 text-xs gap-1.5" onClick={onClose}>
                <X className="size-3.5" />
                Cancel
              </Button>
              <Button
                onClick={handleVerifyAndCommit}
                disabled={!allVerified || verifying}
                className={`h-9 text-xs font-bold gap-2 px-6 transition-all ${
                  allVerified
                    ? "bg-success hover:bg-success/90 text-white shadow-lg shadow-success/20 hover:shadow-success/40 hover:scale-[1.02] active:scale-[0.98]"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {verifying ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />
                    Committing...
                  </>
                ) : (
                  <>
                    <ShieldCheck className="size-4" />
                    Verify & Commit to Staging
                  </>
                )}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ================================================================== */
/* PIPELINE ENTRY ANIMATION (SSE-driven)                               */
/* ================================================================== */
function PipelineEntryAnimation({
  onComplete,
  latestAuditInfo,
}: {
  onComplete: () => void
  latestAuditInfo: { auditId: string; sha256: string; filePath: string } | null
}) {
  const [phases, setPhases] = useState<ParsingPhase[]>(getInitialParsingPhases())
  const [isProcessing, setIsProcessing] = useState(false)
  const [overallResult, setOverallResult] = useState<"pass" | "fail" | null>(null)
  const [showReviewOverlay, setShowReviewOverlay] = useState(false)
  const [completionStats, setCompletionStats] = useState<Record<string, any>>({})
  const phasesRef = useRef<ParsingPhase[]>(getInitialParsingPhases())
  const flowRef = useRef<HTMLDivElement>(null)

  const activePhaseIndex = phases.findIndex((p) => p.status === "active" || p.status === "awaiting_human")

  useEffect(() => {
    if (!latestAuditInfo?.auditId) return

    const apiBase = typeof window !== "undefined"
      ? (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000")
      : "http://127.0.0.1:8000"

    const params = new URLSearchParams({ audit_id: latestAuditInfo.auditId })
    if (latestAuditInfo.filePath) params.set("file_path", latestAuditInfo.filePath)

    setIsProcessing(true)
    const fresh = getInitialParsingPhases()
    phasesRef.current = fresh
    setPhases([...fresh])

    const evtSource = new EventSource(`${apiBase}/api/phase2/process-stream?${params}`)
    let totalLines = 0
    const nodeLineCounts: Record<number, number> = {}

    evtSource.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data)

        if (data.type === "already_processed") {
          evtSource.close()
          // All 5 processing nodes already ran — mark them done, pause at Node 6
          const p = phasesRef.current
          for (let i = 0; i < 5; i++) {
            p[i].status = "success"
            p[i].progress = 100
            p[i].logs = [
              { time: ts(), level: "OK", message: `Already processed (${data.rows} rows staged)` },
            ]
          }
          p[5].status = "awaiting_human"
          p[5].progress = 100
          p[5].logs = [
            { time: ts(), level: "WARN", message: `${data.rows} records staged — awaiting human review` },
            { time: ts(), level: "INFO", message: "Click 'Review Raw Evidence' to inspect and approve" },
          ]
          setPhases([...p])
          setIsProcessing(false)
          setCompletionStats({ rows_processed: data.rows })
          return
        }

        if (data.type === "progress") {
          const p = phasesRef.current
          const pct = data.percent || 0
          for (let i = 0; i < 5; i++) {
            if (p[i].status === "idle") p[i].status = "active"
            p[i].progress = Math.min(pct, 99)
          }
          if (data.message) {
            const phase = p[0]
            phase.logs = [{ time: ts(), level: "INFO", message: data.message }]
          }
          setPhases([...p])
          return
        }

        if (data.type === "init") {
          totalLines = data.total_lines || 1
          return
        }

        if (data.type === "node") {
          const phaseIdx = NODE_TO_PHASE_INDEX[data.node]
          if (phaseIdx === undefined) return
          const p = phasesRef.current

          nodeLineCounts[data.node] = (nodeLineCounts[data.node] || 0) + 1
          const pct = Math.min(100, Math.round((data.line / (totalLines || 1)) * 100))

          // Mark previous phases as success if they aren't already
          for (let i = 0; i < phaseIdx; i++) {
            if (p[i].status !== "success") {
              p[i].status = "success"
              p[i].progress = 100
            }
          }

          const phase = p[phaseIdx]
          if (phase.status === "idle") {
            phase.status = "active"
            phase.logs = [{ time: ts(), level: "INFO", message: `Starting ${phase.label}...` }]
          }
          phase.progress = pct
          // Keep last 30 log lines to avoid memory explosion on large files
          const newLog: LogEntry = { time: ts(), level: "INFO", message: data.msg }
          phase.logs = [...phase.logs.slice(-29), newLog]

          setPhases([...p])
          return
        }

        if (data.type === "complete") {
          evtSource.close()
          const p = phasesRef.current
          // Mark nodes 1-5 as success
          for (let i = 0; i < 5; i++) {
            p[i].status = "success"
            p[i].progress = 100
            if (p[i].logs.length === 0 || p[i].logs[p[i].logs.length - 1]?.level !== "OK") {
              p[i].logs = [...p[i].logs, { time: ts(), level: "OK", message: `COMPLETE` }]
            }
          }
          // Populate stats on phases from completion data
          p[0].stats = [
            { label: "Rows", value: String(data.rows_processed) },
            { label: "Algorithm", value: "SHA-256" },
          ]
          p[1].stats = [
            { label: "Obfuscated", value: String(data.obfuscated_lines || 0) },
            { label: "Cleartext", value: String((data.rows_processed || 0) - (data.obfuscated_lines || 0)) },
          ]
          p[2].stats = [
            { label: "Templates", value: String(data.templates_learned || 0) },
            { label: "Rows", value: String(data.rows_processed) },
          ]
          p[3].stats = [
            { label: "Entities", value: String(data.entities_detected || 0) },
            ...(data.entity_breakdown
              ? Object.entries(data.entity_breakdown as Record<string, number>).slice(0, 3).map(([k, v]) => ({ label: k, value: String(v) }))
              : []),
          ]
          p[4].stats = [
            { label: "Normalized", value: String(data.timestamps_normalized || 0) },
            { label: "Ambiguous", value: String(data.timestamps_ambiguous || 0) },
          ]

          // Node 6 awaits human review
          p[5].status = "awaiting_human"
          p[5].progress = 100
          p[5].logs = [
            { time: ts(), level: "INFO", message: `${data.rows_processed} records staged successfully` },
            { time: ts(), level: "WARN", message: "AWAITING HUMAN: Click 'Review Raw Evidence' to inspect and approve" },
          ]
          setPhases([...p])
          setIsProcessing(false)
          setCompletionStats(data)
          return
        }

        if (data.type === "error") {
          evtSource.close()
          setIsProcessing(false)
          setOverallResult("fail")
          const p = phasesRef.current
          const active = p.findIndex((ph) => ph.status === "active")
          if (active >= 0) {
            p[active].status = "error"
            p[active].logs = [...p[active].logs, { time: ts(), level: "ERROR", message: data.message }]
          }
          setPhases([...p])
          return
        }
      } catch {
        // ignore parse errors
      }
    }

    evtSource.onerror = () => {
      evtSource.close()
      const allDone = phasesRef.current.slice(0, 5).every((ph) => ph.status === "success")
      if (!allDone) {
        setIsProcessing(false)
        const p = phasesRef.current
        const activeIdx = p.findIndex((ph) => ph.status === "active")
        if (activeIdx >= 0) {
          p[activeIdx].logs = [...p[activeIdx].logs, { time: ts(), level: "WARN", message: "Connection lost — refresh to retry" }]
        } else {
          p[0].status = "error"
          p[0].logs = [{ time: ts(), level: "ERROR", message: "Cannot connect to backend — ensure the server is running and refresh" }]
        }
        setPhases([...p])
      }
    }

    return () => evtSource.close()
  }, [latestAuditInfo])

  const handleHumanVerified = useCallback(() => {
    setShowReviewOverlay(false)
    const p = phasesRef.current
    p[5].status = "success"
    p[5].stats = [
      { label: "Records", value: String(completionStats.rows_processed || 0) },
      { label: "Status", value: "COMMITTED" },
    ]
    p[5].logs = [
      ...p[5].logs,
      { time: ts(), level: "OK", message: "HUMAN VERIFICATION COMPLETE: All records approved and committed" },
      { time: ts(), level: "OK", message: "Evidence committed to DuckDB. Phase 3 webhook fired." },
    ]
    setPhases([...p])
    setOverallResult("pass")
    setTimeout(() => onComplete(), 1500)
  }, [onComplete, completionStats])

  return (
    <>
      {showReviewOverlay && (
        <HumanReviewOverlay
          onVerify={handleHumanVerified}
          onClose={() => setShowReviewOverlay(false)}
        />
      )}
      <div className="flex flex-col gap-6 p-6" ref={flowRef}>
        {/* Top Status Bar */}
        <div className="border border-border bg-card p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex size-10 items-center justify-center bg-primary/10">
                <File className="size-5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">Hybrid Parsing & Data Normalization Pipeline</p>
                <div className="flex items-center gap-3 mt-1">
                  {latestAuditInfo ? (
                    <>
                      <span className="font-mono text-xs text-muted-foreground">Source: {latestAuditInfo.filePath || "N/A"}</span>
                      <span className="text-xs text-muted-foreground">SHA-256: {latestAuditInfo.sha256 ? `${latestAuditInfo.sha256.slice(0, 8)}...${latestAuditInfo.sha256.slice(-4)}` : "N/A"}</span>
                      <Badge className="bg-primary/10 text-primary border border-primary/20 hover:bg-primary/10 text-xs">
                        Audit: {latestAuditInfo.auditId.slice(0, 13)}...
                      </Badge>
                    </>
                  ) : (
                    <span className="font-mono text-xs text-muted-foreground">No staging data available</span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {isProcessing && (
                <Badge className="bg-primary/10 text-primary border border-primary/20 hover:bg-primary/10 text-xs gap-1.5 px-3 py-1">
                  <Loader2 className="size-3.5 animate-spin" />
                  Node {activePhaseIndex + 1} / {phases.length}
                </Badge>
              )}
              {!isProcessing && !overallResult && phases[5]?.status === "awaiting_human" && (
                <Badge className="bg-amber-500/10 text-amber-600 border border-amber-500/20 hover:bg-amber-500/10 text-xs gap-1.5 px-3 py-1">
                  <Eye className="size-3.5" />
                  AWAITING HUMAN REVIEW
                </Badge>
              )}
              {overallResult === "pass" && (
                <Badge className="bg-success/10 text-success border border-success/20 hover:bg-success/10 text-xs gap-1.5 px-3 py-1">
                  <CheckCircle2 className="size-3.5" />
                  ALL NODES PASSED
                </Badge>
              )}
              {overallResult === "fail" && (
                <Badge className="bg-destructive/10 text-destructive border border-destructive/20 hover:bg-destructive/10 text-xs gap-1.5 px-3 py-1">
                  <XCircle className="size-3.5" />
                  PIPELINE ERROR
                </Badge>
              )}
            </div>
          </div>

          {/* Mini progress overview */}
          <div className="mt-4 grid grid-cols-6 gap-2">
            {phases.map((phase, i) => (
              <div key={phase.id} className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase truncate">
                    N{i + 1}: {phase.label.split(" ")[0]}
                  </span>
                  <PhaseStatusDot status={phase.status} />
                </div>
                <div className="h-1.5 w-full bg-muted overflow-hidden">
                  <div
                    className={`h-full transition-all duration-200 ${
                      phase.status === "error" ? "bg-destructive"
                      : phase.status === "success" ? "bg-success"
                      : phase.status === "active" ? "bg-primary"
                      : phase.status === "awaiting_human" ? "bg-amber-500"
                      : "bg-muted"
                    }`}
                    style={{ width: `${phase.progress}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Phase Cards */}
        <div className="flex flex-col gap-4">
          {phases.map((phase, index) => (
            <FullPhaseCard
              key={phase.id}
              phase={phase}
              index={index}
              onReviewClick={index === 5 && phase.status === "awaiting_human" ? () => setShowReviewOverlay(true) : undefined}
            />
          ))}
        </div>

        {/* Final Verdict */}
        {overallResult === "pass" && (
          <div className="border-2 border-success/30 bg-success/5 p-8">
            <div className="flex items-start gap-5">
              <div className="flex size-14 items-center justify-center bg-success/10 shrink-0">
                <CheckCircle2 className="size-8 text-success" />
              </div>
              <div className="flex-1">
                <h3 className="text-xl font-bold text-success">Parsing Pipeline Complete — Staging Committed</h3>
                <p className="mt-2 text-sm text-success/80 leading-relaxed">
                  All 6 nodes completed. Officer reviewed and committed evidence records.
                  Transitioning to staging validation interface...
                </p>
                <div className="mt-4 grid grid-cols-4 gap-3">
                  {[
                    { label: "Records Staged", value: String(completionStats.rows_processed || 0) },
                    { label: "Templates Learned", value: String(completionStats.templates_learned || 0) },
                    { label: "Entities Tagged", value: String(completionStats.entities_detected || 0) },
                    { label: "Timestamps OK", value: String(completionStats.timestamps_normalized || 0) },
                  ].map((s) => (
                    <div key={s.label} className="border border-success/20 bg-success/5 p-3 flex flex-col gap-1">
                      <span className="text-[10px] font-semibold tracking-wider text-success/60 uppercase">{s.label}</span>
                      <span className="font-mono text-xs text-success font-bold">{s.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

/* ================================================================== */
/* MAIN COMPONENT                                                      */
/* ================================================================== */
export function ParsingPage() {
  const { setActiveAuditId } = useApp()
  const [showUI, setShowUI] = useState(true)
  const [runPipeline, setRunPipeline] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [currentTablePage, setCurrentTablePage] = useState(1)
  const [copiedRowId, setCopiedRowId] = useState<number | null>(null)
  const rowsPerPage = 8
  const [validationOpen, setValidationOpen] = useState(true)
  const [entityOverrides, setEntityOverrides] = useState<Record<string, string>>({})
  const [committing, setCommitting] = useState(false)
  const [committed, setCommitted] = useState(false)

  const [stagingData, setStagingData] = useState<StagingRow[]>([])
  const [entities, setEntities] = useState<DetectedEntity[]>([])
  const [flags, setFlags] = useState<ValidationFlag[]>([])
  const [latestAuditInfo, setLatestAuditInfo] = useState<{ auditId: string; sha256: string; filePath: string } | null>(null)

  const [serverStats, setServerStats] = useState<Record<string, any> | null>(null)

  const metrics = useMemo(() => ({
    logsParsed: serverStats?.total ?? stagingData.length,
    templatesLearned: serverStats?.has_template_count ?? 0,
    entitiesDetected: serverStats?.has_ner_tags_count ?? entities.length,
    piiDetected: 0,
    ambiguousTimestamps: serverStats?.missing_timestamp_count ?? flags.length,
  }), [serverStats, stagingData.length, entities.length, flags.length])

  useEffect(() => {
    // Load latest audit from Phase 1 (if present) but do not start parsing automatically.
    try {
      const raw = typeof window !== "undefined" ? localStorage.getItem("latest_ingestion_audit") : null
      const parsed = raw ? (JSON.parse(raw) as any) : null
      if (parsed?.auditId) {
        const aid = String(parsed.auditId)
        setLatestAuditInfo({
          auditId: aid,
          sha256: String(parsed.sha256 || ""),
          filePath: String(parsed.filePath || ""),
        })
        setActiveAuditId(aid)

        // Auto-start only if Phase 1 just navigated here (one-time flag).
        const auto = typeof window !== "undefined" ? localStorage.getItem("phase2_autostart_audit") : null
        if (auto && String(auto) === String(parsed.auditId)) {
          localStorage.removeItem("phase2_autostart_audit")
          setShowUI(false)
          setRunPipeline(true)
        }
      }
    } catch {
      // ignore
    }
    loadStagingData()
  }, [])

  const loadStagingData = async () => {
    try {
      const auditId = latestAuditInfo?.auditId || (() => {
        try {
          const raw = typeof window !== "undefined" ? localStorage.getItem("latest_ingestion_audit") : null
          const parsed = raw ? (JSON.parse(raw) as any) : null
          return parsed?.auditId ? String(parsed.auditId) : null
        } catch {
          return null
        }
      })()

      if (!auditId) {
        setStagingData([])
        setEntities([])
        setFlags([])
        setLatestAuditInfo(null)
        return
      }

      // Fetch real statistics from backend (Part G)
      try {
        const stats = await apiClient.getPhase2Statistics(auditId)
        setServerStats(stats)
      } catch {
        setServerStats(null)
      }

      const queryResponse = await apiClient.queryStaging({
        audit_id: auditId,
        status: 'pending',
        limit: 200,
        offset: 0
      })

      const transformedRows: StagingRow[] = []
      const allEntities: DetectedEntity[] = []
      const allFlags: ValidationFlag[] = []
      let firstAuditInfo: { auditId: string; sha256: string; filePath: string } | null = null
      
      for (const entry of queryResponse.entries) {
        try {
          const preview = await apiClient.getStagingPreview(entry.staging_id)
          
          if (!firstAuditInfo && preview.audit) {
            firstAuditInfo = {
              auditId: preview.audit.audit_id,
              sha256: preview.audit.sha256_hash || "",
              filePath: preview.audit.filename || ""
            }
          }
          
          const extractedVars = preview.extracted_variables || {}
          const nerTags = preview.ner_tags || {}
          const decodedPayload = preview.decoded_payload || {}
          
          let rowData = extractedVars.original || decodedPayload.decoded || ""
          if (!rowData && preview.template?.template) {
            rowData = preview.template.template
            Object.entries(extractedVars).forEach(([key, value]) => {
              if (key !== 'original' && key !== 'template') {
                rowData = rowData.replace(`<${key}>`, String(value))
              }
            })
          }
          if (!rowData) rowData = `[Staging ${entry.staging_id}]`
          
          if (nerTags) {
            Object.entries(nerTags).forEach(([type, values]) => {
              const valuesList = Array.isArray(values) ? values : [values]
              valuesList.forEach((value: any) => {
                if (value) {
                  allEntities.push({ type, value: String(value), confidence: 0.85 })
                }
              })
            })
          }

          const ipAddress = (nerTags?.ip_address && (Array.isArray(nerTags.ip_address) ? nerTags.ip_address[0] : nerTags.ip_address)) 
            || extractedVars?.ip_address || extractedVars?.ip || preview.audit?.source_ip || "N/A"
          const user = (nerTags?.user && (Array.isArray(nerTags.user) ? nerTags.user[0] : nerTags.user))
            || extractedVars?.user || extractedVars?.username || "N/A"
          const processName = (nerTags?.process && (Array.isArray(nerTags.process) ? nerTags.process[0] : nerTags.process))
            || extractedVars?.process || extractedVars?.process_name || "N/A"
          const eventTemplate = preview.template?.template || extractedVars?.template || "Unknown template"
          const timestamp = preview.normalized_timestamp || preview.created_at || new Date().toISOString()
          
          if (!preview.normalized_timestamp && preview.extracted_variables) {
            allFlags.push({
              type: "ambiguous_timestamp",
              label: "Ambiguous Timestamp",
              description: "Timestamp could not be normalized"
            })
          }

          transformedRows.push({
            id: transformedRows.length + 1,
            staging_id: entry.staging_id,
            timestamp,
            event_template: eventTemplate,
            ip_address: String(ipAddress),
            process_name: String(processName),
            user: String(user),
            raw_log: String(rowData),
            normalized_fields: JSON.stringify({
              variables: extractedVars,
              ner_tags: nerTags,
              template: preview.template?.template,
              decoded: decodedPayload.decoded
            })
          })
        } catch (previewErr) {
          console.error(`Failed to load preview for staging ${entry.staging_id}:`, previewErr)
        }
      }

      setStagingData(transformedRows)
      setEntities(allEntities)
      setFlags(allFlags)
      setLatestAuditInfo(firstAuditInfo)
    } catch (err) {
      console.error('Failed to load staging data:', err)
      setStagingData([])
      setEntities([])
      setFlags([])
    }
  }

  const filteredRows = useMemo(() => {
    if (!searchQuery.trim()) return stagingData
    const q = searchQuery.toLowerCase()
    return stagingData.filter(
      (r) =>
        r.event_template.toLowerCase().includes(q) ||
        r.ip_address.includes(q) ||
        r.process_name.toLowerCase().includes(q) ||
        r.user.toLowerCase().includes(q) ||
        r.raw_log.toLowerCase().includes(q)
    )
  }, [searchQuery, stagingData])

  const totalPages = Math.ceil(filteredRows.length / rowsPerPage)
  const pagedRows = filteredRows.slice((currentTablePage - 1) * rowsPerPage, currentTablePage * rowsPerPage)

  const copyRowJson = useCallback((row: StagingRow) => {
    navigator.clipboard.writeText(JSON.stringify(row, null, 2))
    setCopiedRowId(row.id)
    setTimeout(() => setCopiedRowId(null), 1500)
  }, [])

  const handleCommit = useCallback(async () => {
    if (!latestAuditInfo?.auditId) return
    setCommitting(true)
    try {
      const overrides = Object.keys(entityOverrides).length > 0 ? entityOverrides : undefined
      await apiClient.commitStagingBatch(latestAuditInfo.auditId, {
        human_overrides: overrides,
        confirm: true,
      })
      setCommitted(true)
      void loadStagingData()
    } catch (err) {
      console.error("Commit failed:", err)
      alert(err instanceof Error ? err.message : "Commit failed")
    } finally {
      setCommitting(false)
    }
  }, [latestAuditInfo, entityOverrides])

  const handleAnimationComplete = useCallback(() => {
    setShowUI(true)
    setRunPipeline(false)
    void loadStagingData()
  }, [])

  if (!showUI) {
    return <PipelineEntryAnimation onComplete={handleAnimationComplete} latestAuditInfo={latestAuditInfo} />
  }

  return (
    <div className="flex flex-col min-h-0 h-full animate-in fade-in duration-500">
      {/* Metrics Cards */}
      <div className="px-6 pt-5 pb-3">
        <div className="grid grid-cols-5 gap-4">
          {[
            { label: "Logs Parsed", value: metrics.logsParsed },
            { label: "Templates Learned", value: metrics.templatesLearned },
            { label: "Entities Detected", value: metrics.entitiesDetected },
            { label: "PII Detected", value: metrics.piiDetected },
            { label: "Ambiguous Timestamps", value: metrics.ambiguousTimestamps },
          ].map((m) => (
            <Card key={m.label} className="border shadow-none">
              <CardContent className="px-4 py-3">
                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-1">{m.label}</p>
                <p className="text-2xl font-bold text-foreground tabular-nums">{m.value}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {!runPipeline && (
        <div className="px-6 pb-4">
          <div className="border border-border bg-card p-4 flex items-center justify-between gap-4">
            <div className="text-xs text-muted-foreground">
              {latestAuditInfo?.auditId
                ? `Ready. Latest audit: ${latestAuditInfo.auditId}`
                : "No Phase 1 upload selected. Upload a file in Phase 1 to enable Phase 2 parsing."}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-[11px]"
                onClick={() => void loadStagingData()}
                disabled={!latestAuditInfo?.auditId}
              >
                Refresh Staging
              </Button>
              <Button
                size="sm"
                className="h-8 text-[11px] font-semibold"
                onClick={() => {
                  if (!latestAuditInfo?.auditId) return
                  setShowUI(false)
                  setRunPipeline(true)
                }}
                disabled={!latestAuditInfo?.auditId}
              >
                Run Phase 2 Parsing
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Main workspace */}
      <div className="flex flex-1 min-h-0 px-6 pb-5 gap-4">
        <div className={`flex flex-col min-h-0 transition-all duration-300 ${validationOpen ? "flex-1" : "w-full"}`}>
          <Card className="border shadow-none flex-1 flex flex-col min-h-0">
            <CardHeader className="px-4 py-3 flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle className="text-sm font-semibold">Staging Data Preview</CardTitle>
                <p className="text-[10px] text-muted-foreground mt-0.5">Data currently in staging area - not committed to forensic database.</p>
              </div>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="size-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <Input placeholder="Search logs..." value={searchQuery} onChange={(e) => { setSearchQuery(e.target.value); setCurrentTablePage(1) }} className="h-7 w-56 pl-8 text-[11px]" />
                </div>
                {!validationOpen && (
                  <Button variant="outline" size="sm" className="h-7 text-[11px] gap-1" onClick={() => setValidationOpen(true)}>
                    <PanelRightOpen className="size-3.5" />
                    Validation
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="flex-1 min-h-0 flex flex-col px-0 pb-0">
              <ScrollArea className="flex-1">
                <div className="overflow-x-auto">
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr className="border-t border-b bg-muted/40">
                        {["#", "Timestamp", "Event Template", "IP Address", "Process", "User", "Actions"].map((h) => (
                          <th key={h} className="px-3 py-2 text-left font-semibold text-muted-foreground uppercase tracking-wider text-[9px]">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {pagedRows.map((row) => (
                        <tr key={row.id} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                          <td className="px-3 py-2 font-mono text-muted-foreground">{row.id}</td>
                          <td className="px-3 py-2 font-mono whitespace-nowrap">{row.timestamp}</td>
                          <td className="px-3 py-2 max-w-[220px] truncate">{row.event_template}</td>
                          <td className="px-3 py-2 font-mono">{row.ip_address}</td>
                          <td className="px-3 py-2">
                            <Badge variant="outline" className="text-[9px] h-4 px-1.5 font-mono">{row.process_name}</Badge>
                          </td>
                          <td className="px-3 py-2">{row.user}</td>
                          <td className="px-3 py-2">
                            <Button variant="ghost" size="sm" className="h-5 w-5 p-0" onClick={() => copyRowJson(row)}>
                              {copiedRowId === row.id ? <Check className="size-3 text-[#198754]" /> : <Copy className="size-3 text-muted-foreground" />}
                            </Button>
                          </td>
                        </tr>
                      ))}
                      {pagedRows.length === 0 && (
                        <tr><td colSpan={7} className="px-3 py-8 text-center text-muted-foreground">No matching records found.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </ScrollArea>
              <div className="flex items-center justify-between border-t px-4 py-2">
                <p className="text-[10px] text-muted-foreground">
                  Showing {(currentTablePage - 1) * rowsPerPage + 1}-{Math.min(currentTablePage * rowsPerPage, filteredRows.length)} of {filteredRows.length} entries
                </p>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="sm" className="h-6 w-6 p-0" disabled={currentTablePage === 1} onClick={() => setCurrentTablePage(1)}><ChevronsLeft className="size-3" /></Button>
                  <Button variant="outline" size="sm" className="h-6 w-6 p-0" disabled={currentTablePage === 1} onClick={() => setCurrentTablePage((p) => p - 1)}><ChevronLeft className="size-3" /></Button>
                  <span className="text-[10px] text-muted-foreground px-2">Page {currentTablePage} of {totalPages || 1}</span>
                  <Button variant="outline" size="sm" className="h-6 w-6 p-0" disabled={currentTablePage >= totalPages} onClick={() => setCurrentTablePage((p) => p + 1)}><ChevronRight className="size-3" /></Button>
                  <Button variant="outline" size="sm" className="h-6 w-6 p-0" disabled={currentTablePage >= totalPages} onClick={() => setCurrentTablePage(totalPages)}><ChevronsRight className="size-3" /></Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* RIGHT COLUMN - Human Validation Panel */}
        {validationOpen && (
          <div className="w-[340px] shrink-0 flex flex-col min-h-0">
            <Card className="border shadow-none flex-1 flex flex-col min-h-0">
              <CardHeader className="px-4 py-3 flex-row items-center justify-between space-y-0">
                <div>
                  <CardTitle className="text-sm font-semibold">Human Validation</CardTitle>
                  <p className="text-[10px] text-muted-foreground mt-0.5">Review & correct entities</p>
                </div>
                <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={() => setValidationOpen(false)}>
                  <X className="size-3.5 text-muted-foreground" />
                </Button>
              </CardHeader>
              <ScrollArea className="flex-1 min-h-0">
                <div className="px-4 pb-4 space-y-5">
                  {committed && (
                    <div className="rounded-md border border-[#198754]/30 bg-[#198754]/5 p-3">
                      <div className="flex items-start gap-2">
                        <ShieldCheck className="size-4 text-[#198754] mt-0.5 shrink-0" />
                        <div>
                          <p className="text-xs font-semibold text-[#198754]">Parsing completed and committed to forensic database.</p>
                          <p className="text-[10px] text-[#198754]/70 mt-0.5">Audit trail recorded. Evidence chain intact.</p>
                        </div>
                      </div>
                    </div>
                  )}
                  <div>
                    <Label className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Detected Entities</Label>
                    <div className="mt-2 space-y-2.5">
                      {entities.length === 0 ? (
                        <p className="text-[10px] text-muted-foreground">No entities detected yet. Upload a file to see detected entities.</p>
                      ) : (
                        entities.map((entity, idx) => {
                          const key = `${entity.type}-${idx}`
                          return (
                            <div key={key} className="space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] font-medium text-foreground">{entity.type}</span>
                                <Badge variant="outline" className="text-[8px] h-3.5 px-1 font-mono">{(entity.confidence * 100).toFixed(0)}%</Badge>
                              </div>
                              <Input
                                className="h-7 text-[11px] font-mono"
                                defaultValue={entityOverrides[key] || entity.value}
                                onChange={(e) => setEntityOverrides((prev) => ({ ...prev, [key]: e.target.value }))}
                              />
                            </div>
                          )
                        })
                      )}
                    </div>
                  </div>
                  <Separator />
                  <div>
                    <Label className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Validation Flags</Label>
                    <div className="mt-2 space-y-2">
                      {flags.length === 0 ? (
                        <p className="text-[10px] text-muted-foreground">No validation flags. All data validated successfully.</p>
                      ) : (
                        flags.map((flag) => (
                          <div key={flag.type} className={`rounded-md border p-2.5 ${
                            flag.type === "ambiguous_timestamp" ? "border-amber-200 bg-amber-50/50"
                            : flag.type === "suspicious_string" ? "border-red-200 bg-red-50/50"
                            : "border-blue-200 bg-blue-50/50"
                          }`}>
                            <div className="flex items-start gap-2">
                              {flag.type === "ambiguous_timestamp" && <AlertTriangle className="size-3.5 text-amber-500 mt-0.5 shrink-0" />}
                              {flag.type === "suspicious_string" && <FileWarning className="size-3.5 text-red-500 mt-0.5 shrink-0" />}
                              {flag.type === "unknown_pattern" && <HelpCircle className="size-3.5 text-blue-500 mt-0.5 shrink-0" />}
                              <div>
                                <p className="text-[10px] font-semibold text-foreground">{flag.label}</p>
                                <p className="text-[9px] text-muted-foreground mt-0.5">{flag.description}</p>
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                  <Separator />
                  <Button className="w-full h-9 text-xs font-semibold bg-[#0B5ED7] hover:bg-[#0B5ED7]/90" disabled={committing || committed || stagingData.length === 0} onClick={handleCommit}>
                    {committing ? (
                      <><Loader2 className="size-3.5 mr-1.5 animate-spin" />Committing...</>
                    ) : committed ? (
                      <><Check className="size-3.5 mr-1.5" />Committed to Database</>
                    ) : (
                      "Confirm & Commit to Database"
                    )}
                  </Button>
                </div>
              </ScrollArea>
            </Card>
          </div>
        )}
      </div>
    </div>
  )
}
