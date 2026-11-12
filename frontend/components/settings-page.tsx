"use client"

import { Settings, Shield, Bell, Database, Clock } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

const configItems = [
  { label: "Encryption Standard", value: "AES-256-GCM", icon: Shield },
  { label: "Authentication Mode", value: "JIT + 2FA", icon: Shield },
  { label: "Session Timeout", value: "30 minutes", icon: Clock },
  { label: "Max Chunk Size", value: "16 MB", icon: Database },
  { label: "WORM Retention Policy", value: "Indefinite", icon: Database },
  { label: "Alert Notifications", value: "Email + SMS", icon: Bell },
]

export function SettingsPage() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="flex items-center gap-2 text-base font-semibold text-foreground">
          <Settings className="size-4 text-primary" />
          System Configuration
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Platform security and operational parameters
        </p>
      </div>

      <Card className="border border-border bg-card">
        <CardHeader className="border-b border-border p-4">
          <CardTitle className="text-sm font-semibold text-foreground">
            Security & Operational Settings
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {configItems.map((item) => (
              <div key={item.label} className="flex items-start gap-3 border border-border p-3">
                <div className="flex size-8 shrink-0 items-center justify-center bg-muted">
                  <item.icon className="size-4 text-primary" />
                </div>
                <div className="flex flex-col gap-1">
                  <p className="text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
                    {item.label}
                  </p>
                  <Badge variant="outline" className="w-fit text-xs font-semibold text-foreground border-border">
                    {item.value}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="border border-border bg-card">
        <CardHeader className="border-b border-border p-4">
          <CardTitle className="text-sm font-semibold text-foreground">
            Compliance Status
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {[
              "IT Act 2000 Compliance",
              "Indian Evidence Act - Section 65B",
              "ISO 27001 Aligned",
              "CERT-In Reporting Enabled",
            ].map((item) => (
              <div key={item} className="flex items-center gap-2 border border-success/20 bg-success/5 p-3">
                <Shield className="size-4 text-success" />
                <span className="text-xs font-medium text-success">{item}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
