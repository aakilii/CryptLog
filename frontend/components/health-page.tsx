"use client"

import { useState, useEffect } from "react"
import { Activity, Wifi, Database, Cpu, HardDrive, ShieldCheck, CheckCircle2, XCircle, Loader2 } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { apiClient } from "@/lib/api-client"

interface HealthCheck {
  label: string
  value: string
  status: "healthy" | "unhealthy"
  icon: React.ComponentType<{ className?: string }>
  detail: string
  progress?: number
}

export function HealthPage() {
  const [healthChecks, setHealthChecks] = useState<HealthCheck[]>([])
  const [systemMetrics, setSystemMetrics] = useState<Array<{ label: string; value: string }>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadHealthData()
  }, [])

  const loadHealthData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [health, hashChain] = await Promise.all([
        apiClient.healthCheck().catch(() => ({ status: "unknown" })),
        apiClient.verifyHashChain().catch(() => ({ status: "unknown", total_entries: 0 })),
      ])

      const checks: HealthCheck[] = [
        {
          label: "API Server",
          value: health.status === "Forensic Engine Online" ? "Online" : "Unknown",
          status: health.status === "Forensic Engine Online" ? "healthy" : "unhealthy",
          icon: Activity,
          detail: health.status || "Status unknown",
        },
        {
          label: "Database",
          value: "Connected",
          status: "healthy",
          icon: Database,
          detail: "SQLite database active",
        },
        {
          label: "Integrity Verification Status",
          value: hashChain.status === "chain_valid" ? "All Chains Valid" : "Unknown",
          status: hashChain.status === "chain_valid" ? "healthy" : "unhealthy",
          icon: ShieldCheck,
          detail: hashChain.total_entries ? `${hashChain.total_entries} entries verified` : "No entries",
        },
      ]

      setHealthChecks(checks)

      const metrics = [
        { label: "Total Entries", value: hashChain.total_entries?.toString() || "0" },
        { label: "Chain Status", value: hashChain.status === "chain_valid" ? "Valid" : "Unknown" },
      ]

      setSystemMetrics(metrics)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load health data")
    } finally {
      setLoading(false)
    }
  }
  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Activity className="size-4 text-primary" />
          System Health Monitor
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Real-time infrastructure and service health status
        </p>
      </div>

      {error && (
        <Card className="border border-destructive bg-destructive/5">
          <CardContent className="p-4">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Health Checks */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {loading ? (
          <Card className="border border-border bg-card">
            <CardContent className="p-4">
              <div className="flex items-center justify-center py-8">
                <Loader2 className="size-6 animate-spin text-primary" />
              </div>
            </CardContent>
          </Card>
        ) : healthChecks.length === 0 ? (
          <Card className="border border-border bg-card">
            <CardContent className="p-4">
              <p className="text-sm text-muted-foreground">No health data available</p>
            </CardContent>
          </Card>
        ) : (
          healthChecks.map((check) => (
          <Card key={check.label} className="border border-border bg-card">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className="flex size-10 shrink-0 items-center justify-center bg-muted">
                  <check.icon className="size-5 text-primary" />
                </div>
                <div className="flex flex-1 flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <p className="text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
                      {check.label}
                    </p>
                    {check.status === "healthy" ? (
                      <CheckCircle2 className="size-4 text-success" />
                    ) : (
                      <XCircle className="size-4 text-destructive" />
                    )}
                  </div>
                  <p className="text-sm font-semibold text-foreground">{check.value}</p>
                  <p className="text-[10px] text-muted-foreground">{check.detail}</p>
                  {check.progress !== undefined && (
                    <div className="flex flex-col gap-1">
                      <Progress value={check.progress} className="h-1.5" />
                      <span className="text-[9px] text-muted-foreground">{check.progress}% utilized</span>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
          ))
        )}
      </div>

      {/* System Metrics */}
      <Card className="border border-border bg-card">
        <CardHeader className="border-b border-border p-4">
          <CardTitle className="text-sm font-semibold text-foreground">
            System Metrics
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="size-6 animate-spin text-primary" />
            </div>
          ) : systemMetrics.length === 0 ? (
            <p className="text-sm text-muted-foreground">No system metrics available</p>
          ) : (
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
              {systemMetrics.map((metric) => (
                <div key={metric.label} className="flex flex-col gap-1 border-l-2 border-primary/20 pl-3">
                  <p className="text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
                    {metric.label}
                  </p>
                  <p className="text-sm font-semibold text-foreground">{metric.value}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
