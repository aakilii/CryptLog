"use client"

import { useState, useEffect } from "react"
import { ShieldAlert, Search, AlertTriangle, Bug, FileWarning, Clock, Loader2 } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
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

interface QuarantinedFile {
  id: string
  fileName: string
  sha256: string
  reason: string
  detail: string
  timestamp: string
  severity: "critical" | "warning"
  sourceIp: string
}

const reasonIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  "Zip Bomb": AlertTriangle,
  "Malware": Bug,
  "Header Mismatch": FileWarning,
}

export function QuarantinePage() {
  const [quarantinedFiles, setQuarantinedFiles] = useState<QuarantinedFile[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadQuarantinedFiles()
  }, [])

  const loadQuarantinedFiles = async () => {
    try {
      setLoading(true)
      setError(null)
      const ledgerResponse = await apiClient.listLedger(200, 0, "")
      const quarantined = (ledgerResponse.items || [])
        .filter((entry: any) => entry.status === "quarantined")
        .map((entry: any) => ({
          id: entry.id,
          fileName: entry.filename || "Unknown",
          sha256: entry.sha256_hash ? `${entry.sha256_hash.slice(0, 12)}...${entry.sha256_hash.slice(-4)}` : "N/A",
          reason: "Quarantined",
          detail: "File quarantined during ingestion",
          timestamp: entry.upload_time || "",
          severity: "critical" as const,
          sourceIp: entry.source_ip || "Unknown",
        }))
      setQuarantinedFiles(quarantined)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load quarantined files")
    } finally {
      setLoading(false)
    }
  }
  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
          <ShieldAlert className="size-4 text-destructive" />
          Quarantine Center
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Isolated suspicious files pending forensic review
        </p>
      </div>

      {error && (
        <Card className="border border-destructive bg-destructive/5">
          <CardContent className="p-4">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="border-l-2 border-l-destructive bg-card">
          <CardContent className="p-4">
            <p className="text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
              Total Quarantined
            </p>
            <p className="text-2xl font-bold text-destructive">
              {loading ? "..." : quarantinedFiles.length}
            </p>
          </CardContent>
        </Card>
        <Card className="border-l-2 border-l-destructive bg-card">
          <CardContent className="p-4">
            <p className="text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
              Critical Severity
            </p>
            <p className="text-2xl font-bold text-destructive">
              {loading ? "..." : quarantinedFiles.filter((f) => f.severity === "critical").length}
            </p>
          </CardContent>
        </Card>
        <Card className="border-l-2 border-l-[#D97706] bg-card">
          <CardContent className="p-4">
            <p className="text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
              Warnings
            </p>
            <p className="text-2xl font-bold text-[#D97706]">
              {loading ? "..." : quarantinedFiles.filter((f) => f.severity === "warning").length}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      <Card className="border border-destructive/20 bg-card">
        <CardHeader className="border-b border-destructive/10 bg-destructive/5 p-4">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold text-destructive">
            <ShieldAlert className="size-4" />
            Suspicious Files
          </CardTitle>
        </CardHeader>
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 hover:bg-muted/50">
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">ID</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">File Name</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">SHA-256</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Reason</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Detail</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Timestamp</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8">
                  <Loader2 className="mx-auto size-6 animate-spin text-primary" />
                </TableCell>
              </TableRow>
            ) : quarantinedFiles.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  No quarantined files
                </TableCell>
              </TableRow>
            ) : (
              quarantinedFiles.map((file) => {
                const ReasonIcon = reasonIcons[file.reason] || AlertTriangle
                return (
                  <TableRow key={file.id}>
                    <TableCell className="font-mono text-xs font-bold text-destructive">{file.id}</TableCell>
                    <TableCell className="text-xs font-medium text-foreground">{file.fileName}</TableCell>
                    <TableCell className="font-mono text-[10px] text-muted-foreground">{file.sha256}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <ReasonIcon className="size-3.5 text-destructive" />
                        <Badge className={
                          file.severity === "critical"
                            ? "bg-destructive/10 text-destructive border border-destructive/20 hover:bg-destructive/10 text-[10px]"
                            : "bg-[#D97706]/10 text-[#D97706] border border-[#D97706]/20 hover:bg-[#D97706]/10 text-[10px]"
                        }>
                          {file.reason}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="max-w-48 text-[10px] text-muted-foreground">{file.detail}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Clock className="size-3 text-muted-foreground" />
                        <span className="font-mono text-[10px] text-muted-foreground">{file.timestamp}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 gap-1 border-destructive/30 text-[10px] text-destructive hover:bg-destructive/5"
                      >
                        <Search className="size-3" />
                        Investigate
                      </Button>
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
