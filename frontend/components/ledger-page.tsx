"use client"

import { useState, useEffect } from "react"
import { CheckCircle2, Download, Link2, ShieldCheck, XCircle, Loader2, Search } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { apiClient, LedgerEntry } from "@/lib/api-client"

export function LedgerPage() {
  const [ledgerEntries, setLedgerEntries] = useState<LedgerEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [chainValid, setChainValid] = useState<boolean | null>(null)
  const [isVerifying, setIsVerifying] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [limit] = useState(200)
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)

  useEffect(() => {
    loadLedger()
  }, [offset, searchQuery])

  const loadLedger = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await apiClient.listLedger(limit, offset, searchQuery)
      setLedgerEntries(response.items || [])
      setTotal(response.total || 0)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load ledger entries")
    } finally {
      setLoading(false)
    }
  }

  const verifyChain = async () => {
    setIsVerifying(true)
    setChainValid(null)
    try {
      const result = await apiClient.verifyHashChain()
      setChainValid(result.status === "chain_valid")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to verify chain")
      setChainValid(false)
    } finally {
      setIsVerifying(false)
    }
  }

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 B"
    const k = 1024
    const sizes = ["B", "KB", "MB", "GB", "TB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
  }

  const formatDate = (dateString: string): string => {
    try {
      return new Date(dateString).toLocaleString("en-US", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    } catch {
      return dateString
    }
  }

  const truncateHash = (hash: string, length: number = 12): string => {
    if (!hash) return "N/A"
    if (hash.length <= length * 2) return hash
    return `${hash.slice(0, length)}...${hash.slice(-4)}`
  }

  const exportCSV = () => {
    const headers = ["Block", "Filename", "SHA-256", "Previous Hash", "Merkle Root", "Mode", "Size", "Upload Time", "Status"]
    const rows = ledgerEntries.map((entry, i) => [
      (total - offset - i).toString(),
      entry.filename || "",
      entry.sha256_hash || "",
      entry.previous_hash || "",
      entry.merkle_root || "",
      entry.ingestion_mode || "",
      formatFileSize(entry.file_size || 0),
      formatDate(entry.upload_time),
      entry.status || "",
    ])

    const csv = [headers.join(","), ...rows.map(row => row.map(cell => `"${cell}"`).join(","))].join("\n")
    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `ledger_export_${new Date().toISOString().split("T")[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
            <Link2 className="size-4 text-primary" />
            Forensic Evidence Ledger
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Blockchain-style immutable log chain with cryptographic verification
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            onClick={verifyChain}
            disabled={isVerifying}
            className="bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {isVerifying ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Verifying...
              </>
            ) : (
              <>
                <ShieldCheck className="mr-2 size-4" />
                Verify Chain
              </>
            )}
          </Button>
          <Button
            variant="outline"
            className="border-border text-foreground"
            onClick={exportCSV}
            disabled={ledgerEntries.length === 0}
          >
            <Download className="mr-2 size-4" />
            Export CSV
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by filename, hash, or mode..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              setOffset(0)
            }}
            className="pl-9"
          />
        </div>
      </div>

      {/* Integrity Indicator */}
      {chainValid !== null && (
        <Card className={`border ${chainValid ? "border-success/30 bg-success/5" : "border-destructive/30 bg-destructive/5"}`}>
          <CardContent className="flex items-center gap-3 p-4">
            {chainValid ? (
              <>
                <CheckCircle2 className="size-5 text-success" />
                <div>
                  <p className="text-sm font-semibold text-success">Chain Integrity Verified</p>
                  <p className="text-[10px] text-success/80">
                    All {total} blocks validated. No tampering detected. Verified at {new Date().toISOString()}
                  </p>
                </div>
              </>
            ) : (
              <>
                <XCircle className="size-5 text-destructive" />
                <div>
                  <p className="text-sm font-semibold text-destructive">Chain Integrity Compromised</p>
                  <p className="text-[10px] text-destructive/80">Hash mismatch detected. Immediate investigation required.</p>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* Ledger Table */}
      <Card className="border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 hover:bg-muted/50">
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Block</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Filename</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">SHA-256</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Previous Hash</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Merkle Root</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Mode</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Size</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Upload Time</TableHead>
              <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={10} className="text-center py-8">
                  <Loader2 className="mx-auto size-6 animate-spin text-primary" />
                </TableCell>
              </TableRow>
            ) : ledgerEntries.length === 0 ? (
              <TableRow>
                <TableCell colSpan={10} className="text-center text-muted-foreground py-8">
                  No ledger entries found
                </TableCell>
              </TableRow>
            ) : (
              ledgerEntries.map((entry, i) => (
                <TableRow key={entry.id || i}>
                  <TableCell className="font-mono text-xs font-bold text-primary">
                    #{total - offset - i}
                  </TableCell>
                  <TableCell className="text-xs font-medium text-foreground">
                    {entry.filename || "Unknown"}
                  </TableCell>
                  <TableCell className="font-mono text-[10px] text-muted-foreground">
                    {truncateHash(entry.sha256_hash || "")}
                  </TableCell>
                  <TableCell className="font-mono text-[10px] text-muted-foreground">
                    <div className="flex items-center gap-1">
                      {i < ledgerEntries.length - 1 && entry.previous_hash && (
                        <Link2 className="size-3 text-primary" />
                      )}
                      {truncateHash(entry.previous_hash || "")}
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-[10px] text-muted-foreground">
                    {entry.merkle_root ? truncateHash(entry.merkle_root) : "N/A"}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[10px] text-foreground border-border">
                      {entry.ingestion_mode || "Manual"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-foreground">
                    {formatFileSize(entry.file_size || 0)}
                  </TableCell>
                  <TableCell className="font-mono text-[10px] text-muted-foreground">
                    {formatDate(entry.upload_time)}
                  </TableCell>
                  <TableCell>
                    <Badge className="bg-success/10 text-success border border-success/20 hover:bg-success/10 text-[10px]">
                      {entry.status || "committed"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
