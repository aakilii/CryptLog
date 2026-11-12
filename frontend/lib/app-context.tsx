"use client"

import React, { createContext, useContext, useState, useCallback, useEffect } from "react"
import { authService } from "./auth-service"

export type Page =
  | "login"
  | "register"
  | "dashboard"
  | "ingestion"
  | "parsing"
  | "phase3"
  | "ledger"
  | "quarantine"
  | "audit"
  | "health"
  | "settings"

const ACTIVE_AUDIT_STORAGE_KEY = "csic_active_audit_id"

interface AppContextType {
  currentPage: Page
  setCurrentPage: (page: Page) => void
  /** Phase 1 ledger UUID — drives Phase 3–4 live datasets when set */
  activeAuditId: string | null
  setActiveAuditId: (auditId: string | null) => void
  isAuthenticated: boolean
  user: { id: string; email: string; full_name: string | null; is_admin: boolean } | null
  register: (email: string, password: string, fullName?: string) => Promise<void>
  login: (email: string, password: string, otp?: string) => Promise<void>
  logout: () => Promise<void>
  officerName: string
}

const AppContext = createContext<AppContextType | null>(null)

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [currentPage, setCurrentPage] = useState<Page>("login")
  const [activeAuditId, setActiveAuditIdState] = useState<string | null>(null)
  const [authState, setAuthState] = useState(authService.getState())

  useEffect(() => {
    if (typeof window === "undefined") return
    try {
      const v = localStorage.getItem(ACTIVE_AUDIT_STORAGE_KEY)
      if (v) setActiveAuditIdState(v)
    } catch {
      /* ignore */
    }
  }, [])

  const setActiveAuditId = useCallback((auditId: string | null) => {
    setActiveAuditIdState(auditId)
    if (typeof window === "undefined") return
    try {
      if (auditId) localStorage.setItem(ACTIVE_AUDIT_STORAGE_KEY, auditId)
      else localStorage.removeItem(ACTIVE_AUDIT_STORAGE_KEY)
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    const unsubscribe = authService.subscribe((state) => {
      setAuthState(state)
      if (!state.isAuthenticated) {
        setCurrentPage("login")
      } else if (currentPage === "login") {
        setCurrentPage("dashboard")
      }
    })

    // Check if user is already authenticated
    if (authState.isAuthenticated && currentPage === "login") {
      setCurrentPage("dashboard")
    }

    return () => {
      unsubscribe()
    }
  }, [currentPage, authState.isAuthenticated])

  const register = useCallback(async (email: string, password: string, fullName?: string) => {
    try {
      await authService.register({ email, password, full_name: fullName })
      // After registration, automatically log in
      await authService.login({ email, password })
      setCurrentPage("dashboard")
    } catch (error) {
      throw error
    }
  }, [])

  const login = useCallback(async (email: string, password: string, otp?: string) => {
    try {
      await authService.login({ email, password, otp })
      setCurrentPage("dashboard")
    } catch (error) {
      throw error
    }
  }, [])

  const logout = useCallback(async () => {
    await authService.logout()
    setCurrentPage("login")
  }, [])

  return (
    <AppContext.Provider
      value={{
        currentPage,
        setCurrentPage,
        activeAuditId,
        setActiveAuditId,
        isAuthenticated: authState.isAuthenticated,
        user: authState.user,
        register,
        login,
        logout,
        officerName: authState.user?.full_name || "Dir. Rajesh Kumar, IPS",
      }}
    >
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const context = useContext(AppContext)
  if (!context) throw new Error("useApp must be used within AppProvider")
  return context
}
