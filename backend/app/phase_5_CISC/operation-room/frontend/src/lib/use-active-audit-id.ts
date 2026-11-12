"use client"

import { useState, useEffect } from "react"

/** Same key as csic_frontend AppProvider — Phase 2–4 pipeline audit UUID. */
const ACTIVE_AUDIT_STORAGE_KEY = "csic_active_audit_id"

export function useActiveAuditId(): string | null {
  const [id, setId] = useState<string | null>(null)

  useEffect(() => {
    function read() {
      try {
        setId(localStorage.getItem(ACTIVE_AUDIT_STORAGE_KEY))
      } catch {
        setId(null)
      }
    }
    read()
    window.addEventListener("storage", read)
    window.addEventListener("focus", read)
    return () => {
      window.removeEventListener("storage", read)
      window.removeEventListener("focus", read)
    }
  }, [])

  return id
}
