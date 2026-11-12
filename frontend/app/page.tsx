"use client"

import React, { Suspense } from "react"
import { AppProvider, useApp } from "@/lib/app-context"
import { LoginPage } from "@/components/login-page"
import { RegisterPage } from "@/components/register-page"
import { AppSidebar } from "@/components/app-sidebar"
import { TopNavbar } from "@/components/top-navbar"
import { DashboardPage } from "@/components/dashboard-page"
import { IngestionPage } from "@/components/ingestion-page"
import { LedgerPage } from "@/components/ledger-page"
import { QuarantinePage } from "@/components/quarantine-page"
import { AuditPage } from "@/components/audit-page"
import { HealthPage } from "@/components/health-page"
import { SettingsPage } from "@/components/settings-page"
import { ParsingPage } from "@/components/parsing-page"
import { Phase3Page } from "@/components/phase3-page"
import { MasterLayout } from "@/components/master-layout"
import { AppUrlBridge } from "@/components/app-url-bridge"

function AppContent() {
  const { isAuthenticated, currentPage } = useApp()
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-muted">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    )
  }

  if (!isAuthenticated) {
    if (currentPage === "register") {
      return <RegisterPage />
    }
    return <LoginPage />
  }

  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen flex-col items-center justify-center bg-muted">
          <div className="text-muted-foreground text-sm">Loading workspace…</div>
        </div>
      }
    >
      <AppUrlBridge />
      <MasterLayout>
        {currentPage === "dashboard" && <DashboardPage />}
        {currentPage === "ingestion" && <IngestionPage />}
        {currentPage === "parsing" && <ParsingPage />}
        {currentPage === "phase3" && <Phase3Page />}
        {currentPage === "ledger" && <LedgerPage />}
        {currentPage === "quarantine" && <QuarantinePage />}
        {currentPage === "audit" && <AuditPage />}
        {currentPage === "health" && <HealthPage />}
        {currentPage === "settings" && <SettingsPage />}
      </MasterLayout>
    </Suspense>
  )
}

export default function Page() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  )
}
