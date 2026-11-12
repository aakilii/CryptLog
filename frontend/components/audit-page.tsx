"use client"

import { useState, useEffect } from "react"
import { ClipboardList, User, Shield, FileText, LogIn, LogOut, Search as SearchIcon, Eye, Loader2 } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { apiClient } from "@/lib/api-client"

interface AuditEntry {
  id: string
  timestamp: string
  officer: string
  action: string
  target: string
  ip: string
  level: "info" | "warning" | "critical"
}

const actionIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  FILE_INGESTED: FileText,
  FILE_QUARANTINED: Shield,
  LEDGER_VERIFIED: ClipboardList,
  MALWARE_DETECTED: Shield,
  SESSION_START: LogIn,
  SESSION_END: LogOut,
  HEADER_MISMATCH: Eye,
}

const levelColors: Record<string, string> = {
  info: "bg-primary/10 text-primary border-primary/20",
  warning: "bg-[#D97706]/10 text-[#D97706] border-[#D97706]/20",
  critical: "bg-destructive/10 text-destructive border-destructive/20",
}

export function AuditPage() {
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadAuditEntries()
  }, [])

  const loadAuditEntries = async () => {
    try {
      setLoading(true)
      setError(null)
      const ledgerResponse = await apiClient.listLedger(200, 0, "")
      const entries: AuditEntry[] = (ledgerResponse.items || []).map((entry: any) => ({
        id: entry.id,
        timestamp: entry.upload_time || "",
        officer: entry.uploader || "System",
        action: entry.status === "quarantined" ? "FILE_QUARANTINED" : "FILE_INGESTED",
        target: entry.filename || "Unknown",
        ip: entry.source_ip || "Unknown",
        level: entry.status === "quarantined" ? "warning" : "info",
      }))
      setAuditEntries(entries)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit entries")
    } finally {
      setLoading(false)
    }
  }
  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
          <ClipboardList className="size-4 text-primary" />
          Audit Trail
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Complete forensic audit log of all system operations
        </p>
      </div>

      {error && (
        <Card className="border border-destructive bg-destructive/5">
          <div className="p-4">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        </Card>
      )}

      <Card className="border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 hover:bg-muted/50">
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">ID</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Timestamp</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Officer</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Action</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Target</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Source IP</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Level</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  <Loader2 className="mx-auto size-6 animate-spin text-primary" />
                </TableCell>
              </TableRow>
            ) : auditEntries.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No audit entries found
                </TableCell>
              </TableRow>
            ) : (
              auditEntries.map((entry) => {
                const ActionIcon = actionIcons[entry.action] || FileText
                return (
                  <TableRow key={entry.id}>
                    <TableCell className="font-mono text-xs text-muted-foreground">{entry.id}</TableCell>
                    <TableCell className="font-mono text-[10px] text-muted-foreground">{entry.timestamp}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <User className="size-3 text-muted-foreground" />
                        <span className="text-xs text-foreground">{entry.officer}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <ActionIcon className="size-3 text-primary" />
                        <span className="font-mono text-[10px] font-medium text-foreground">{entry.action}</span>
                      </div>
                    </TableCell>
                    <TableCell className="max-w-48 text-xs text-muted-foreground">{entry.target}</TableCell>
                    <TableCell className="font-mono text-[10px] text-muted-foreground">{entry.ip}</TableCell>
                    <TableCell>
                      <Badge className={`border ${levelColors[entry.level]} hover:${levelColors[entry.level]} text-[10px]`}>
                        {entry.level.toUpperCase()}
                      </Badge>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
