"use client"

import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import {
  LayoutDashboard,
  Upload,
  BookOpen,
  ShieldAlert,
  ClipboardList,
  Activity,
  ChevronDown,
  ChevronRight,
  Workflow,
  Database,
  Settings,
} from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarFooter,
  SidebarSeparator,
} from "@/components/ui/sidebar"
import { useApp } from "@/lib/app-context"
import type { ShellPage } from "@/lib/app-navigation"
import { isShellGlassChrome } from "@/lib/shell-chrome"
import { useShellNavigate } from "@/lib/use-shell-navigate"

const ingestionSubItems: { id: ShellPage; label: string; icon: typeof Upload }[] = [
  { id: "ingestion", label: "Injection Control", icon: Upload },
  { id: "ledger", label: "Ledger View", icon: BookOpen },
  { id: "quarantine", label: "Quarantine Center", icon: ShieldAlert },
  { id: "audit", label: "Audit Trails", icon: ClipboardList },
  { id: "health", label: "System Health", icon: Activity },
]

const parsingSubItems: { id: ShellPage; label: string; icon: typeof Upload }[] = [
  { id: "parsing", label: "Parsing Pipeline", icon: Workflow },
]

const phase3SubItems: { id: ShellPage; label: string; icon: typeof Upload }[] = [
  { id: "phase3", label: "Hot/Cold DB", icon: Database },
]

function IconBox({ active, colorHex, children }: { active: boolean; colorHex: string; children: React.ReactNode }) {
  const boxStyle = {
    backgroundColor: active ? colorHex : "#f1f5f9",
    color: active ? "#ffffff" : colorHex,
  }

  return (
    <div style={boxStyle} className="flex size-7 shrink-0 items-center justify-center rounded-lg transition-all duration-300 shadow-sm">
      {children}
    </div>
  )
}

function StatusDot({ colorHex }: { colorHex: string }) {
  return (
    <div style={{ backgroundColor: colorHex }} className="size-1.5 rounded-full ml-auto shrink-0 shadow-sm" />
  )
}

export function AppSidebar({ className }: { className?: string }) {
  const { currentPage } = useApp()
  const { go } = useShellNavigate()
  const router = useRouter()
  const searchParams = useSearchParams()

  const [ingestionOpen, setIngestionOpen] = useState(
    ingestionSubItems.some((item) => item.id === currentPage)
  )
  const [parsingOpen, setParsingOpen] = useState(currentPage === "parsing")
  const [phase3Open, setPhase3Open] = useState(currentPage === "phase3")

  const isIngestionSection = ingestionSubItems.some((item) => item.id === currentPage)
  const isParsingSection = currentPage === "parsing"
  const isPhase3Section = currentPage === "phase3"

  const new_ = "Main Dashboard"

  const activeStyle = {
    border: "2px solid #3b82f6",
    backgroundColor: "#eff6ff",
    color: "#1d4ed8",
    fontWeight: "700",
    borderRadius: "0.75rem"
  }

  const inactiveStyle = {
    border: "2px solid transparent",
    color: "#64748b",
    fontWeight: "600",
    borderRadius: "0.75rem"
  }

  const activeSubStyle = {
    color: "#2563eb",
    fontWeight: "700",
    backgroundColor: "#eff6ff",
    borderRadius: "0.5rem"
  }

  const inactiveSubStyle = {
    color: "#64748b",
    fontWeight: "500",
    borderRadius: "0.5rem"
  }

  const glassChrome = isShellGlassChrome(currentPage)

  const sidebarSurface = glassChrome
    ? {
        background:
          "linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(248, 250, 252, 0.9) 45%, rgba(241, 245, 249, 0.86) 100%)",
        borderRight: "1px solid rgba(148, 163, 184, 0.38)",
        backdropFilter: "blur(14px) saturate(1.1)",
        WebkitBackdropFilter: "blur(14px) saturate(1.1)",
        boxShadow:
          "inset -1px 0 0 rgba(255, 255, 255, 0.65), 6px 0 32px -10px rgba(15, 23, 42, 0.12), 2px 0 16px -6px rgba(59, 130, 246, 0.1)",
        width: "280px",
        minWidth: "280px",
        fontFamily: "'Inter', system-ui, sans-serif",
      }
    : {
        backgroundColor: "#fafaf9",
        borderRight: "1px solid #e2e8f0",
        width: "280px",
        minWidth: "280px",
        fontFamily: "'Inter', system-ui, sans-serif",
      }

  return (
    <Sidebar variant="sidebar" collapsible="icon" style={sidebarSurface} className="z-40 transition-all duration-300 m-0 p-0 rounded-none">

      <SidebarHeader className="px-5 py-6">
        <div className="flex items-center gap-3">

          <div
            className="flex shrink-0 items-center justify-center rounded-full bg-white border border-slate-200 shadow-sm overflow-hidden"
            style={{ width: "48px", height: "48px", minWidth: "48px", minHeight: "48px" }}
          >
            <img
              src="/sakshi-logo.jpg"
              alt="Sakshi Ledger Logo"
              style={{ width: "100%", height: "100%", objectFit: "cover", transform: "scale(1.25)" }}
            />
          </div>

          <div className="flex flex-col gap-0 group-data-[collapsible=icon]:hidden">
            <span style={{ color: "#0f172a", letterSpacing: "-0.02em" }} className="text-[16px] font-extrabold">SAKSHI LEDGER</span>
            <span style={{ color: "#64748b" }} className="text-[9px] font-bold">From Digital Traces to Defensible Truth</span>
          </div>

        </div>
      </SidebarHeader>

      <SidebarContent className="overflow-x-hidden px-3">

        <div className="h-4" />

        <SidebarGroup>
          <SidebarGroupLabel style={{ color: "#94a3b8", letterSpacing: "0.05em" }} className="text-[9px] font-bold uppercase mb-2 px-2">
            Security Protocol Phases
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <button
                  onClick={() => go("dashboard")}
                  style={currentPage === "dashboard" ? activeStyle : inactiveStyle}
                  className="flex items-center w-full gap-3 px-3 py-2 transition-all hover:bg-slate-100"
                >
                  <IconBox active={currentPage === "dashboard"} colorHex="#f59e0b">
                    <LayoutDashboard className="size-3.5" />
                  </IconBox>
                  <span className="flex-1 text-left text-sm font-bold">{new_}</span>
                  <StatusDot colorHex="#fbbf24" />
                </button>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <div className="h-3" />

        <SidebarGroup>
          <SidebarGroupLabel style={{ color: "#94a3b8", letterSpacing: "0.05em" }} className="text-[9px] font-bold uppercase mb-2 px-2">
            Investigation Modules
          </SidebarGroupLabel>
          <SidebarGroupContent className="flex flex-col gap-1">
            <SidebarMenu>

              <SidebarMenuItem>
                <button
                  onClick={() => {
                    setIngestionOpen(!ingestionOpen)
                    if (!isIngestionSection) go("ingestion")
                  }}
                  style={isIngestionSection ? activeStyle : inactiveStyle}
                  className="flex items-center w-full gap-3 px-3 py-2 transition-all hover:bg-slate-100"
                >
                  <IconBox active={isIngestionSection} colorHex="#3b82f6">
                    <Upload className="size-3.5" />
                  </IconBox>
                  <span className="flex-1 text-left text-sm font-bold">Ingestion</span>
                  <StatusDot colorHex="#22d3ee" />
                </button>
              </SidebarMenuItem>

              {ingestionOpen && (
                <div style={{ borderLeft: "2px solid #cbd5e1" }} className="ml-6 pl-2.5 mt-1 flex flex-col gap-0.5">
                  {ingestionSubItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => go(item.id)}
                      style={currentPage === item.id ? activeSubStyle : inactiveSubStyle}
                      className="flex items-center w-full gap-3 px-3 py-1.5 transition-colors hover:bg-slate-100"
                    >
                      <span className="flex-1 text-left text-xs font-medium">{item.label}</span>
                    </button>
                  ))}
                </div>
              )}

              <div className="h-1" />

              <SidebarMenuItem>
                <button
                  onClick={() => {
                    setParsingOpen(!parsingOpen)
                    if (!isParsingSection) go("parsing")
                  }}
                  style={isParsingSection ? activeStyle : inactiveStyle}
                  className="flex items-center w-full gap-3 px-3 py-2 transition-all hover:bg-slate-100"
                >
                  <IconBox active={isParsingSection} colorHex="#10b981">
                    <Workflow className="size-3.5" />
                  </IconBox>
                  <span className="flex-1 text-left text-sm font-bold">Parsing</span>
                  <StatusDot colorHex="#34d399" />
                </button>
              </SidebarMenuItem>

              {parsingOpen && (
                <div style={{ borderLeft: "2px solid #cbd5e1" }} className="ml-6 pl-2.5 mt-1 flex flex-col gap-0.5">
                  {parsingSubItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => go(item.id)}
                      style={currentPage === item.id ? activeSubStyle : inactiveSubStyle}
                      className="flex items-center w-full gap-3 px-3 py-1.5 transition-colors hover:bg-slate-100"
                    >
                      <span className="flex-1 text-left text-xs font-medium">{item.label}</span>
                    </button>
                  ))}
                </div>
              )}

              <div className="h-1" />

              <SidebarMenuItem>
                <button
                  onClick={() => {
                    setPhase3Open(!phase3Open)
                    if (!isPhase3Section) go("phase3")
                  }}
                  style={isPhase3Section ? activeStyle : inactiveStyle}
                  className="flex items-center w-full gap-3 px-3 py-2 transition-all hover:bg-slate-100"
                >
                  <IconBox active={isPhase3Section} colorHex="#6366f1">
                    <Database className="size-3.5" />
                  </IconBox>
                  <span className="flex-1 text-left text-sm font-bold">Data Storage</span>
                  <StatusDot colorHex="#818cf8" />
                </button>
              </SidebarMenuItem>

              {phase3Open && (
                <div style={{ borderLeft: "2px solid #cbd5e1" }} className="ml-6 pl-2.5 mt-1 flex flex-col gap-0.5">
                  {phase3SubItems.map((item) => (
                    <button
                      key={item.id}
                      onClick={() => go(item.id)}
                      style={currentPage === item.id ? activeSubStyle : inactiveSubStyle}
                      className="flex items-center w-full gap-3 px-3 py-1.5 transition-colors hover:bg-slate-100"
                    >
                      <span className="flex-1 text-left text-xs font-medium">{item.label}</span>
                    </button>
                  ))}
                </div>
              )}

            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <div className="h-4" />

        <SidebarGroup>
          <SidebarGroupLabel style={{ color: "#94a3b8", letterSpacing: "0.05em" }} className="text-[9px] font-bold uppercase mb-2 px-2">
            Execution Phase
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <button
                  onClick={() => router.push("/operation-room")}
                  style={inactiveStyle}
                  className="flex items-center w-full gap-3 px-3 py-2 transition-all hover:bg-slate-100"
                >
                  <IconBox active={false} colorHex="#f43f5e">
                    <Activity className="size-3.5" />
                  </IconBox>
                  <span className="flex-1 text-left text-sm font-bold">Operation Room</span>
                  <StatusDot colorHex="#fb7185" />
                </button>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <div className="h-4" />

        <SidebarGroup>
          <SidebarGroupLabel style={{ color: "#94a3b8", letterSpacing: "0.05em" }} className="text-[9px] font-bold uppercase mb-2 px-2">
            System Control
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <button
                  onClick={() => go("settings")}
                  style={currentPage === "settings" ? activeStyle : inactiveStyle}
                  className="flex items-center w-full gap-3 px-3 py-2 transition-all hover:bg-slate-100"
                >
                  <IconBox active={currentPage === "settings"} colorHex="#64748b">
                    <Settings className="size-3.5" />
                  </IconBox>
                  <span className="flex-1 text-left text-sm font-bold">Settings</span>
                  <StatusDot colorHex="#94a3b8" />
                </button>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

      </SidebarContent>

    </Sidebar>
  )
}