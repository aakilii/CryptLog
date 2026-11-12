"use client"

import { useState, useEffect } from "react"
import { FileText, Shield, ShieldAlert, Link2, CheckCircle2, Loader2, ScanSearch } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts"
import { apiClient } from "@/lib/api-client"
import { formatDistanceToNow } from "date-fns"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"

interface DashboardData {
  summary: any
  timeline: any
  severity: any
  recentUploads: any[]
  hashChainStatus: any
}

export function DashboardPage() {
  const router = useRouter()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [mounted, setMounted] = useState(false)

  const openOperationRoom = () => {
    router.push("/operation-room")
  }

  useEffect(() => {
    setMounted(true)
    loadDashboardData()
  }, [])

  const loadDashboardData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [summary, timeline, severity, recentUploads, hashChain] = await Promise.all([
        apiClient
          .getDashboardSummary()
          .catch(() => ({
            total_logs: 0,
            total_sessions: 0,
            quarantined_files: 0,
            active_alerts: 0,
            total_events: 0,
          })),
        apiClient.getDashboardTimeline().catch(() => ({ timeline: [], series: [] })),
        apiClient.getDashboardSeverity().catch(() => ({
          severity_distribution: [
            { level: "critical", count: 0 },
            { level: "warning", count: 0 },
            { level: "info", count: 0 },
          ],
        })),
        apiClient.getRecentUploads().catch(() => []),
        apiClient.verifyHashChain().catch(() => ({ status: "unknown", total_entries: 0 })),
      ])

      setData({
        summary,
        timeline,
        severity,
        recentUploads: recentUploads || [],
        hashChainStatus: hashChain,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard data")
    } finally {
      setLoading(false)
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
        timeZone: "UTC",
        timeZoneName: "short",
      })
    } catch {
      return dateString
    }
  }

  if (!mounted || loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive" className="m-6">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  const summary = data?.summary || {}
  const hashChain = data?.hashChainStatus || {}
  const recentUploadsArray = Array.isArray(data?.recentUploads) ? data.recentUploads : []
  const recentLogs = recentUploadsArray.slice(0, 10)

  const metrics = [
    {
      label: "Total Logs Ingested",
      value: (summary.total_logs ?? 0).toLocaleString(),
      icon: FileText,
      trend:
        typeof summary.total_events === "number" && summary.total_events > 0
          ? `${summary.total_events.toLocaleString()} events in analytics store`
          : summary.latest_log
            ? `Latest analytics: ${formatDistanceToNow(new Date(summary.latest_log as string), { addSuffix: true })}`
            : "Ledger count — run feature pipeline for analytics totals",
      color: "text-primary",
      borderColor: "border-primary/30",
    },
    {
      label: "Active JIT Sessions",
      value: (summary.total_sessions ?? 0).toString(),
      icon: Shield,
      trend: "Unexpired, unused ingestion sessions",
      color: "text-success",
      borderColor: "border-success/30",
    },
    {
      label: "Quarantined Files",
      value: (summary.quarantined_files ?? 0).toString(),
      icon: ShieldAlert,
      trend: `${summary.active_alerts ?? 0} critical alerts (detection)`,
      color: "text-destructive",
      borderColor: "border-destructive/30",
    },
    {
      label: "Ledger Integrity Status",
      value: hashChain.status === "chain_valid" ? "Chain Valid" : "Unknown",
      icon: Link2,
      trend: hashChain.total_entries ? `${hashChain.total_entries} entries` : "No entries",
      color: hashChain.status === "chain_valid" ? "text-success" : "text-muted-foreground",
      borderColor: hashChain.status === "chain_valid" ? "border-success/30" : "border-muted/30",
      isValid: hashChain.status === "chain_valid",
    },
  ]

  const timelineArray = Array.isArray(data?.timeline?.timeline) ? data.timeline.timeline : []
  const lineData = timelineArray.map((item: any) => ({
    date: new Date(item.timestamp).toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    }),
    logs: item.count ?? 0,
  }))

  const barData = [
    { mode: "Manual", count: recentLogs.filter((l: any) => l.ingestion_mode === "manual").length },
    { mode: "Cloud", count: recentLogs.filter((l: any) => l.ingestion_mode === "cloud").length },
    { mode: "Agentless", count: recentLogs.filter((l: any) => l.ingestion_mode === "agentless_telemetry").length },
  ]

  const cleanCount = recentLogs.filter((l: any) => l.status === "ingested" || l.status === "clean").length
  const quarantinedCount = recentLogs.filter((l: any) => l.status === "quarantined").length
  const pieData = [
    { name: "Clean", value: cleanCount, fill: "#198754" },
    { name: "Quarantined", value: quarantinedCount, fill: "#DC2626" },
  ]

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Section 1: Overview Metrics */}
      <section>
        <h3 className="mb-4 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
          Overview Metrics
        </h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => (
            <Card
              key={metric.label}
              className={`border-l-2 ${metric.borderColor} bg-card`}
            >
              <CardContent className="flex items-start gap-4 p-4">
                <div className={`flex size-10 shrink-0 items-center justify-center bg-muted ${metric.color}`}>
                  <metric.icon className="size-5" />
                </div>
                <div className="flex flex-col gap-1">
                  <p className="text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
                    {metric.label}
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-xl font-bold text-foreground">
                      {metric.value}
                    </span>
                    {metric.isValid && (
                      <CheckCircle2 className="size-4 text-success" />
                    )}
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    {metric.trend}
                  </p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Section 2: Analytics Graphs */}
      <section>
        <h3 className="mb-4 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
          Analytics
        </h3>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          {/* Line Chart */}
          <Card className="border border-border bg-card xl:col-span-2">
            <CardHeader className="border-b border-border p-4">
              <CardTitle className="text-sm font-semibold text-foreground">
                Logs Ingested Over Time
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={lineData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#D1D5DB" />
                    <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748B" }} />
                    <YAxis
                      tick={{ fontSize: 11, fill: "#64748B" }}
                      tickFormatter={(v) =>
                        v >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${v}`
                      }
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#fff",
                        border: "1px solid #D1D5DB",
                        borderRadius: "2px",
                        fontSize: "12px",
                      }}
                      formatter={(v: number) => [v.toLocaleString(), "Logs"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="logs"
                      stroke="#0B5ED7"
                      strokeWidth={2}
                      dot={{ fill: "#0B5ED7", r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Bar + Pie vertical stack */}
          <div className="flex flex-col gap-4">
            <Card className="border border-border bg-card">
              <CardHeader className="border-b border-border p-4">
                <CardTitle className="text-sm font-semibold text-foreground">
                  Ingestion Mode Distribution
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="h-[120px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={barData} layout="vertical">
                      <XAxis type="number" tick={{ fontSize: 10, fill: "#64748B" }} />
                      <YAxis dataKey="mode" type="category" tick={{ fontSize: 11, fill: "#64748B" }} width={70} />
                      <Tooltip
                        contentStyle={{
                          background: "#fff",
                          border: "1px solid #D1D5DB",
                          borderRadius: "2px",
                          fontSize: "12px",
                        }}
                      />
                      <Bar dataKey="count" fill="#0B5ED7" radius={[0, 2, 2, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card className="border border-border bg-card">
              <CardHeader className="border-b border-border p-4">
                <CardTitle className="text-sm font-semibold text-foreground">
                  Clean vs Quarantined
                </CardTitle>
              </CardHeader>
              <CardContent className="flex items-center justify-center p-4">
                <div className="h-[120px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={30}
                        outerRadius={50}
                        dataKey="value"
                        paddingAngle={2}
                      >
                        {pieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.fill} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          background: "#fff",
                          border: "1px solid #D1D5DB",
                          borderRadius: "2px",
                          fontSize: "12px",
                        }}
                        formatter={(v: number) => [v.toLocaleString(), "Files"]}
                      />
                      <Legend
                        wrapperStyle={{ fontSize: "11px" }}
                        iconType="square"
                        iconSize={8}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Section 3: Recent Logs Table */}
      <section>
        <h3 className="mb-4 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
          Recent Logs
        </h3>
        <Card className="border border-border bg-card">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50 hover:bg-muted/50">
                <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">File Name</TableHead>
                <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">SHA-256</TableHead>
                <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Merkle Root</TableHead>
                <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Mode</TableHead>
                <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Size</TableHead>
                <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Status</TableHead>
                <TableHead className="text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">Upload Time (UTC)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {recentLogs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                    No recent uploads
                  </TableCell>
                </TableRow>
              ) : (
                recentLogs.map((log: any, i: number) => (
                  <TableRow key={log.id || i}>
                    <TableCell className="text-xs font-medium text-foreground">{log.filename || "Unknown"}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {log.sha256_hash ? `${log.sha256_hash.slice(0, 12)}...${log.sha256_hash.slice(-4)}` : "N/A"}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {log.merkle_root ? `${log.merkle_root.slice(0, 12)}...${log.merkle_root.slice(-4)}` : "N/A"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-[10px] font-medium text-foreground border-border">
                        {log.ingestion_mode || "Manual"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-foreground">{formatFileSize(log.file_size || 0)}</TableCell>
                    <TableCell>
                      <Badge
                        className={
                          log.status === "ingested" || log.status === "clean"
                            ? "bg-success/10 text-success border border-success/20 hover:bg-success/10"
                            : "bg-destructive/10 text-destructive border border-destructive/20 hover:bg-destructive/10"
                        }
                      >
                        {log.status === "ingested" ? "Clean" : log.status || "Unknown"}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {formatDate(log.upload_time)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Card>
      </section>
    </div>
  )
}
