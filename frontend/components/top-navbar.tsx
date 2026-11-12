"use client"

import { useState } from "react"
import { LogOut, Shield, User } from "lucide-react"
import { useApp } from "@/lib/app-context"
import { isShellGlassChrome } from "@/lib/shell-chrome"
import { cn } from "@/lib/utils"

const pageLabels: Record<string, string> = {
  dashboard: "MAIN DASHBOARD",
  ingestion: "INGESTION CONTROL",
  ledger: "LEDGER VIEW",
  quarantine: "QUARANTINE CENTER",
  audit: "AUDIT TRAILS",
  health: "SYSTEM HEALTH",
  parsing: "PARSING & NORMALIZATION",
  phase3: "HOT & COLD STORAGE",
  settings: "SETTINGS",
}

export function TopNavbar({ className }: { className?: string }) {
  const { currentPage, officerName, logout } = useApp()
  const [dropdownOpen, setDropdownOpen] = useState(false)

  const new_ = "National Forensic Log Intelligence Platform"

  const glassChrome = isShellGlassChrome(currentPage)

  const headerSurface = glassChrome
    ? {
        height: "80px" as const,
        minHeight: "80px" as const,
        background:
          "linear-gradient(135deg, rgba(255, 255, 255, 0.94) 0%, rgba(248, 250, 252, 0.88) 38%, rgba(239, 246, 255, 0.82) 72%, rgba(241, 245, 249, 0.9) 100%)",
        borderBottom: "1px solid rgba(148, 163, 184, 0.38)",
        backdropFilter: "blur(14px) saturate(1.15)",
        WebkitBackdropFilter: "blur(14px) saturate(1.15)",
        boxShadow:
          "inset 0 1px 0 rgba(255, 255, 255, 0.75), 0 10px 40px -12px rgba(15, 23, 42, 0.14), 0 4px 20px -6px rgba(59, 130, 246, 0.12)",
      }
    : {
        height: "80px" as const,
        minHeight: "80px" as const,
        backgroundColor: "#fafaf9",
        borderBottom: "1px solid #e2e8f0",
      }

  return (
    <header
      style={headerSurface}
      className={cn(
        "flex shrink-0 w-full items-center justify-between px-8 lg:px-12 m-0 transition-all",
        glassChrome ? "relative z-30" : "z-30",
        className
      )}
    >

      <div className="flex items-center pl-2 lg:pl-4">
        <div className="hidden flex-col gap-1 sm:flex">
          <h3 style={{ color: "#0f172a" }} className="text-2xl font-extrabold tracking-tight">
            {pageLabels[currentPage] || "Main Dashboard"}
          </h3>
          <p style={{ color: "#64748b" }} className="text-xs uppercase tracking-widest font-bold">
            {new_}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-8 lg:gap-10">

        <div className="hidden items-center gap-3 md:flex mr-4">
          <span className="relative flex size-3">
            <span style={{ backgroundColor: "#34d399" }} className="absolute inline-flex size-full animate-ping rounded-full opacity-75" />
            <span style={{ backgroundColor: "#10b981" }} className="relative inline-flex size-3 rounded-full" />
          </span>
          <span style={{ backgroundColor: "#ecfdf5", color: "#047857", border: "1px solid #a7f3d0" }} className="text-sm font-bold px-4 py-2 rounded-full shadow-sm">
            Session Active
          </span>
        </div>

        <div style={{ backgroundColor: "#e2e8f0" }} className="hidden h-10 w-px md:block" />

        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            style={{ backgroundColor: "#ffffff", border: "1px solid #e2e8f0" }}
            className="flex h-12 w-12 items-center justify-center rounded-full hover:bg-slate-50 transition-all shadow-sm"
          >
            <User style={{ color: "#9333ea" }} className="size-6" />
          </button>

          {dropdownOpen && (
            <div style={{ backgroundColor: "#ffffff", border: "1px solid #e2e8f0" }} className="absolute right-0 mt-4 w-72 rounded-3xl shadow-xl p-3 z-50">

              <div className="px-4 py-4 flex items-center gap-4 border-b border-slate-100 mb-3">
                <div style={{ backgroundColor: "#faf5ff", border: "1px solid #e9d5ff" }} className="flex size-12 items-center justify-center rounded-full shrink-0">
                  <Shield style={{ color: "#9333ea" }} className="size-6" />
                </div>
                <div className="flex flex-col gap-0.5">
                  <span style={{ color: "#0f172a" }} className="text-base font-bold">{officerName}</span>
                  <span style={{ color: "#64748b" }} className="text-[11px] font-bold uppercase tracking-wider">Level-5 Clearance</span>
                </div>
              </div>

              <button
                onClick={() => {
                  setDropdownOpen(false)
                  logout()
                }}
                style={{ backgroundColor: "#fff1f2", color: "#e11d48" }}
                className="flex w-full items-center gap-3 px-4 py-3 text-base font-bold hover:opacity-80 rounded-xl transition-all"
              >
                <LogOut className="size-5" />
                Logout
              </button>
            </div>
          )}
        </div>

      </div>
    </header>
  )
}